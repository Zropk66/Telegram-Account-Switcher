"""进程管理."""

import atexit
import ctypes
import hashlib
import os
import subprocess
import sys
import threading
import weakref
from contextlib import contextmanager, suppress
from ctypes import wintypes
from pathlib import Path
from typing import Callable, Generator, Optional

from src.core.config import ConfigService
from src.core.constants import LaunchMode
from src.core.exceptions import TASException
from src.core.logger import Logger
from src.core.process_service import PsutilProcessService
from src.core.runtime import delay

_should_reap: bool = True
_active_managers = weakref.WeakSet()
_hook_process_pool: dict[str, int] = {}

_INVALID_HANDLE_VALUE = (1 << (64 if sys.maxsize > 2**32 else 32)) - 1

_pm_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_pm_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
_pm_kernel32.CreateFileW.restype = wintypes.HANDLE

_pm_kernel32.WriteFile.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
_pm_kernel32.WriteFile.restype = wintypes.BOOL

_pm_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_pm_kernel32.CloseHandle.restype = wintypes.BOOL


class _WIN32_FIND_DATAW(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("dwReserved0", wintypes.DWORD),
        ("dwReserved1", wintypes.DWORD),
        ("cFileName", wintypes.WCHAR * 260),
        ("cAlternateFileName", wintypes.WCHAR * 14),
    ]


_pm_kernel32.FindFirstFileW.argtypes = [
    wintypes.LPCWSTR, ctypes.POINTER(_WIN32_FIND_DATAW),
]
_pm_kernel32.FindFirstFileW.restype = wintypes.HANDLE

_pm_kernel32.FindNextFileW.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(_WIN32_FIND_DATAW),
]
_pm_kernel32.FindNextFileW.restype = wintypes.BOOL

_pm_kernel32.FindClose.argtypes = [wintypes.HANDLE]
_pm_kernel32.FindClose.restype = wintypes.BOOL


def _set_should_reap(value: bool) -> None:
    """设置是否释放句柄."""
    global _should_reap
    _should_reap = value


class ProcessManager:
    """进程管理器."""

    def __init__(
        self,
        process_service: Optional[PsutilProcessService] = None,
        config: Optional[ConfigService] = None,
        logger: Optional[Logger] = None,
    ) -> None:
        """初始化进程管理器."""
        self._popen_ref: Optional[subprocess.Popen] = None
        self._process_service = process_service or PsutilProcessService()
        self._config = config or ConfigService()
        self._logger = logger or Logger()
        _active_managers.add(self)

    def _reap_popen(self) -> None:
        """释放子进程资源."""
        if not _should_reap:
            return
        if self._popen_ref is not None:
            with suppress(Exception):
                self._popen_ref.poll()
            self._popen_ref = None

    @contextmanager
    def kill_and_guard(self, client_name: str, restart_on_exit: bool = False) -> Generator[None, None, None]:
        """关闭并防护进程."""
        self.kill_process(client_name)
        try:
            yield
        finally:
            if restart_on_exit:
                self.start_process(wait=False)

    def start_process(
        self,
        wait: bool = True,
        tdata_name: Optional[str] = None,
        tray_name: Optional[str] = None,
        force_symlink: bool = False,
    ) -> bool:
        """启动客户端进程.

        Args:
            wait: 是否等待进程就绪.
            tdata_name: hook 模式下的自定义 tdata 目录名.
            tray_name: hook 模式下的托盘/窗口显示标签名.
            force_symlink: 强制使用链接模式（用于 hook 降级）.
        """
        try:
            full_path = Path(self._config.path) / self._config.client

            if not full_path.exists():
                self._logger.error(f"找不到客户端可执行文件: {full_path}")
                return False

            self._reap_popen()

            if not force_symlink and self._config.launch_mode == LaunchMode.HOOK:
                return self._start_with_hook(full_path, tdata_name, tray_name, wait)
            return self._start_with_symlink(full_path, wait)

        except (FileNotFoundError, PermissionError) as e:
            self._logger.error(f"启动失败: {e}")
            return False
        except Exception as e:
            self._logger.error(f"启动过程出现未预期错误: {e}")
            return False

    def _start_with_hook(
        self,
        full_path: Path,
        tdata_name: Optional[str],
        tray_name: Optional[str],
        wait: bool,
    ) -> bool:
        """使用 hook 注入器启动客户端进程."""
        from src.core.injecter import launch_with_hook

        src_dir = Path(__file__).resolve().parent.parent
        dll_path = src_dir / "hook" / "hook.dll"

        if not dll_path.exists():
            self._logger.error(f"找不到 hook DLL: {dll_path}")
            return False

        self._logger.debug(
            f"启动 hook 模式: exe={full_path}, dll={dll_path}, "
            f"tdata={tdata_name}, tray={tray_name}"
        )

        try:
            pid = launch_with_hook(
                telegram_path=str(full_path),
                dll_path=str(dll_path),
                logger=self._logger,
                tdata_name=tdata_name,
                tray_name=tray_name,
                isolate_appid=self._config.isolate_appid,
            )
            if pid is None:
                self._logger.error("hook 注入失败")
                return False

            if tdata_name:
                _hook_process_pool[tdata_name] = pid

            if not wait:
                return True

            return self._wait_for_ready()
        except Exception as e:
            self._logger.error(f"hook 启动异常: {e}")
            return False

    def is_target_running(self, target_folder: str) -> bool:
        """检查特定 target_folder 的 hook 实例是否在运行."""
        pid = _hook_process_pool.get(target_folder)
        if pid and not self._process_service.wait_for_process(pid, timeout=0.001):
            return True

        import psutil

        client_name = self._config.client
        for proc_info in self._process_service.find_processes(client_name):
            try:
                proc = psutil.Process(proc_info.pid)
                env = proc.environ()
                if env.get("TDATA_NAME") == target_folder:
                    _hook_process_pool[target_folder] = proc_info.pid
                    return True
            except Exception:
                continue

        return False

    def _cleanup_exited_pids(self) -> None:
        """清理 _hook_process_pool 中已退出的 PID."""
        import psutil

        to_remove = [
            folder for folder, pid in _hook_process_pool.items()
            if not psutil.pid_exists(pid)
        ]
        for folder in to_remove:
            del _hook_process_pool[folder]

    def get_running_instances(self) -> list[tuple[str, str, int]]:
        """获取所有运行中的 hook 实例列表."""
        self._cleanup_exited_pids()
        result: list[tuple[str, str, int]] = []

        for target_folder, pid in list(_hook_process_pool.items()):
            if self._process_service.wait_for_process(pid, timeout=0.001):
                continue

            tag_name = target_folder
            for tag, info in self._config.tags.items():
                if info.get("folder") == target_folder:
                    tag_name = tag
                    break
            else:
                if target_folder == self._config.get_account(self._config.default).get("folder"):
                    tag_name = self._config.default

            result.append((tag_name, target_folder, pid))

        return result

    def forward_url(self, url: str, target_folder: str) -> bool:
        """通过 hook 注入启动临时进程，将 tg:// URL 转发到已运行实例."""
        from src.core.injecter import launch_with_hook

        full_path = Path(self._config.path) / self._config.client
        if not full_path.exists():
            self._logger.error(f"找不到客户端可执行文件: {full_path}")
            return False

        src_dir = Path(__file__).resolve().parent.parent
        dll_path = src_dir / "hook" / "hook.dll"
        if not dll_path.exists():
            self._logger.error(f"找不到 hook DLL: {dll_path}")
            return False

        self._logger.debug(f"转发 URL 到 '{target_folder}': {url}")

        try:
            pid = launch_with_hook(
                telegram_path=str(full_path),
                dll_path=str(dll_path),
                logger=self._logger,
                tdata_name=target_folder,
                extra_args=url,
            )
            if pid is not None:
                self._logger.info(f"URL 已转发至 PID={pid} (target={target_folder})")
                return True
            self._logger.error("URL 转发失败：hook 注入未成功")
            return False
        except Exception as e:
            self._logger.error(f"URL 转发失败: {e}")
            return False

    def forward_url_symlink(self, url: str) -> bool:
        """在链接模式下转发 tg:// URL（直接启动 Telegram 并传入 URL）."""
        full_path = Path(self._config.path) / self._config.client
        if not full_path.exists():
            self._logger.error(f"找不到客户端可执行文件: {full_path}")
            return False

        self._logger.debug(f"转发 URL (链接模式): {url}")
        try:
            proc = subprocess.Popen(
                args=[str(full_path), url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                shell=False,
                start_new_session=True,
            )
            self._logger.info(f"URL 已转发 (链接模式) PID={proc.pid}")
            return True
        except Exception as e:
            self._logger.error(f"URL 转发失败: {e}")
            return False

    def forward_url_direct(self, url: str, target_folder: str) -> bool:
        """直接连接到已有实例的命名管道，转发 tg:// URL."""
        self._cleanup_exited_pids()
        path_hash = self._get_path_hash()

        self._logger.debug(
            f"forward_url_direct: hash={path_hash}, target='{target_folder}'"
        )

        pipe_name = self._find_instance_pipe(path_hash, target_folder)
        if not pipe_name:
            self._logger.debug(
                f"未找到匹配管道 (hash={path_hash}, target={target_folder})"
            )
            return False

        full_pipe_path = f"\\\\.\\pipe\\{pipe_name}"
        self._logger.debug(f"连接管道: {full_pipe_path}")

        handle = _pm_kernel32.CreateFileW(
            full_pipe_path,
            0xC0000000,
            0,
            None,
            3,
            0,
            None,
        )

        if handle is None or handle == _INVALID_HANDLE_VALUE:
            err = ctypes.get_last_error()
            self._logger.debug(f"管道连接失败: error={err}")
            return False

        try:
            command = f"OPEN:{url};"
            cmd_bytes = command.encode("latin-1")
            written = wintypes.DWORD(0)

            success = _pm_kernel32.WriteFile(
                handle, cmd_bytes, len(cmd_bytes), ctypes.byref(written), None
            )

            if not success:
                err = ctypes.get_last_error()
                self._logger.debug(f"管道写入失败: error={err}")
                return False

            self._logger.info(
                f"URL 已通过管道直接转发: {url} (written={written.value} bytes)"
            )

            import time
            time.sleep(0.3)
            return True
        finally:
            _pm_kernel32.CloseHandle(handle)

    def wait_for_instance(self, target_folder: str, timeout: float = 5.0) -> bool:
        """等待指定实例的命名管道可用."""
        import time

        path_hash = self._get_path_hash()

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._find_instance_pipe(path_hash, target_folder):
                return True
            time.sleep(0.2)
        return False

    def find_running_instances_by_pipes(self) -> list[tuple[str, str]]:
        """通过管道枚举查找运行中的实例."""
        path_hash = self._get_path_hash()

        target_folders: set[str] = set()
        default_folder = self._config.get_account(self._config.default).get("folder") or "tdata"
        target_folders.add(default_folder)

        for tag, info in self._config.tags.items():
            folder = info.get("folder")
            if folder:
                target_folders.add(folder)

        result: list[tuple[str, str]] = []
        for folder in target_folders:
            pipe_name = self._find_instance_pipe(path_hash, folder)
            if pipe_name:
                tag_name = folder
                for tag, info in self._config.tags.items():
                    if info.get("folder") == folder:
                        tag_name = tag
                        break
                else:
                    if folder == default_folder:
                        tag_name = self._config.default
                result.append((tag_name, folder))

        self._logger.debug(f"管道枚举找到 {len(result)} 个运行实例: {result}")
        return result

    def _get_path_hash(self) -> str:
        """计算工作目录的 MD5 哈希，用于命名管道匹配."""
        workdir = os.path.abspath(self._config.path).replace("\\", "/")
        if len(workdir) > 3 and workdir.endswith("/"):
            workdir = workdir[:-1]
        return hashlib.md5(workdir.encode("utf-8")).hexdigest()

    def _find_instance_pipe(
        self, path_hash: str, target_folder: str
    ) -> Optional[str]:
        """枚举命名管道，找到目标实例的管道名."""
        find_data = _WIN32_FIND_DATAW()
        search_handle = _pm_kernel32.FindFirstFileW(
            r"\\.\pipe\*", ctypes.byref(find_data)
        )

        if search_handle is None or search_handle == _INVALID_HANDLE_VALUE:
            self._logger.debug("FindFirstFileW 失败: 无管道")
            return None

        suffix = f"_{target_folder}"
        hash_prefix = f"Global\\{path_hash}-"

        try:
            while True:
                name = find_data.cFileName
                if suffix in name and hash_prefix in name:
                    self._logger.debug(f"匹配到管道: {name}")
                    return name
                if not _pm_kernel32.FindNextFileW(
                    search_handle, ctypes.byref(find_data)
                ):
                    break
        finally:
            _pm_kernel32.FindClose(search_handle)

        self._logger.debug(
            f"管道枚举结束，未找到匹配 (prefix={hash_prefix}, suffix={suffix})"
        )
        return None

    def bring_to_foreground(self, target_folder: str) -> None:
        """置顶特定账号的窗口."""
        pid = _hook_process_pool.get(target_folder)
        if not pid:
            self._logger.debug(f"置顶跳过：进程池中无 '{target_folder}' 的 PID 记录")
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            user32.GetForegroundWindow.restype = wintypes.HWND
            user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            user32.IsWindowVisible.argtypes = [wintypes.HWND]
            user32.IsWindowVisible.restype = wintypes.BOOL
            user32.IsIconic.argtypes = [wintypes.HWND]
            user32.IsIconic.restype = wintypes.BOOL
            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.ShowWindow.restype = wintypes.BOOL
            user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            user32.SetForegroundWindow.restype = wintypes.BOOL
            user32.BringWindowToTop.argtypes = [wintypes.HWND]
            user32.BringWindowToTop.restype = wintypes.BOOL
            user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
            user32.AttachThreadInput.restype = wintypes.BOOL
            user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
            user32.EnumWindows.restype = wintypes.BOOL
            user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
            user32.GetWindowTextLengthW.restype = ctypes.c_int
            user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_void_p]
            kernel32.GetCurrentThreadId.restype = wintypes.DWORD

            target_pids = {pid}
            try:
                import psutil

                parent_proc = psutil.Process(pid)
                for child in parent_proc.children(recursive=True):
                    target_pids.add(child.pid)
            except Exception:
                pass

            self._logger.debug(f"置顶搜索 PID 集合: {target_pids}")

            target_hwnd: Optional[int] = None

            def enum_windows_callback(hwnd, extra):
                nonlocal target_hwnd
                if not user32.IsWindowVisible(hwnd):
                    return True
                if user32.GetWindowTextLengthW(hwnd) <= 0:
                    return True
                window_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                if window_pid.value in target_pids:
                    target_hwnd = hwnd
                    return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)

            if not target_hwnd:
                self._logger.debug(f"未找到 PID={target_pids} 对应的可视窗口")
                return

            self._logger.debug(f"找到目标窗口 HWND={target_hwnd}")

            if user32.IsIconic(target_hwnd):
                user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE

            current_tid = kernel32.GetCurrentThreadId()
            foreground_hwnd = user32.GetForegroundWindow()
            foreground_tid = user32.GetWindowThreadProcessId(foreground_hwnd, None) if foreground_hwnd else 0
            target_tid = user32.GetWindowThreadProcessId(target_hwnd, None)

            self._logger.debug(
                f"current_tid={current_tid} foreground_tid={foreground_tid} target_tid={target_tid}"
            )

            VK_MENU = 0x12  # noqa: N806
            KEYEVENTF_KEYUP = 0x0002  # noqa: N806
            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

            attached_fg = False
            attached_target = False
            if foreground_tid and foreground_tid != current_tid:
                attached_fg = bool(user32.AttachThreadInput(current_tid, foreground_tid, True))
            if target_tid and target_tid != current_tid:
                attached_target = bool(user32.AttachThreadInput(current_tid, target_tid, True))

            self._logger.debug(f"AttachThreadInput: fg={attached_fg} target={attached_target}")

            try:
                user32.BringWindowToTop(target_hwnd)
                result = bool(user32.SetForegroundWindow(target_hwnd))
            finally:
                if attached_fg:
                    user32.AttachThreadInput(current_tid, foreground_tid, False)
                if attached_target:
                    user32.AttachThreadInput(current_tid, target_tid, False)

            self._logger.debug(f"SetForegroundWindow result={result} HWND={target_hwnd}")
        except Exception as e:
            self._logger.debug(f"置顶窗口异常: {e}")

    def _start_with_symlink(self, full_path: Path, wait: bool) -> bool:
        """使用普通方式启动客户端进程."""
        if not wait:
            self._logger.debug(f"启动进程: {full_path}")
            proc = subprocess.Popen(
                args=[str(full_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                shell=False,
                start_new_session=True,
            )
            self._popen_ref = proc
            return True

        self._logger.debug(f"启动并等待就绪: {full_path}")
        proc = subprocess.Popen(
            args=[str(full_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            shell=False,
            start_new_session=True,
        )
        self._popen_ref = proc

        return self._wait_for_ready()

    def _wait_for_ready(self) -> bool:
        """等待进程就绪."""
        try:
            if self._popen_ref is not None:
                import ctypes

                res = ctypes.windll.user32.WaitForInputIdle(int(self._popen_ref._handle), 10000)
                if res == 0:
                    return True
        except Exception as e:
            self._logger.debug(f"WaitForInputIdle 失败，使用备用检测方法: {e}")

        max_time = 15
        poll_interval = 0.1
        elapsed = 0.0
        success = False

        while elapsed < max_time:
            if self._popen_ref is not None and self._popen_ref.poll() is None:
                success = True
                break
            if self._process_service.find_processes(self._config.client):
                success = True
                break
            delay(poll_interval)
            elapsed += poll_interval

        if not success:
            self._logger.warning(f"等待进程启动超时 ({max_time}s)")

        return success

    def kill_process(self, client: str) -> bool:
        """杀死指定客户端进程."""
        self._reap_popen()

        if not isinstance(client, str):
            raise TypeError(f"client 名称必须是字符串，实际为 {type(client)}")

        killed = False
        processes_to_kill = self._process_service.find_processes(client)

        if not processes_to_kill:
            return False

        self._logger.debug(f"正在清理 {len(processes_to_kill)} 个 {client} 进程...")

        for proc_info in processes_to_kill:
            if self._process_service.terminate(proc_info.pid):
                killed = True

        delay(0.1)

        remaining = self._process_service.find_processes(client)
        for proc_info in remaining:
            if self._process_service.kill(proc_info.pid):
                killed = True

        if self._process_service.find_processes(client):
            raise TASException(f"权限不足，无法终止进程: {client} 请手动关闭或以管理员身份运行.")

        return killed


class ProcessMonitor:
    """进程状态监视器."""

    def __init__(
        self,
        process_name: str,
        *,
        check_interval: float = 0.5,
        test_mode: bool = False,
        logger: Optional[Logger] = None,
        process_service: Optional[PsutilProcessService] = None,
    ) -> None:
        """初始化进程监视器."""
        self.process_name = process_name
        self.check_interval = check_interval
        self._watch_thread = None
        self._stop_event = threading.Event()
        self._logger = logger or Logger()
        self._process_service = process_service or PsutilProcessService()
        self.last_PID = None
        self._test_mode = test_mode
        self._callbacks: list[Callable[[bool, Optional[int]], None]] = []
        self._pid_callbacks: dict[int, list[Callable[[bool, Optional[int]], None]]] = {}

    @contextmanager
    def watch(self, callback: Callable[[bool, Optional[int]], None]) -> Generator["ProcessMonitor", None, None]:
        """管理监控生命周期."""
        self.register_callback(callback)
        self.start_watching()
        try:
            yield self
        finally:
            self.unregister_callback(callback)
            self.stop_watching()

    def register_callback(
        self,
        callback: Callable[[bool, Optional[int]], None],
        pid: Optional[int] = None,
    ) -> None:
        """注册状态变化回调。指定 pid 时仅在该进程状态变化时收到通知。"""
        if pid is not None:
            if pid not in self._pid_callbacks:
                self._pid_callbacks[pid] = []
            if callback not in self._pid_callbacks[pid]:
                self._pid_callbacks[pid].append(callback)
        else:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[bool, Optional[int]], None]) -> None:
        """注销状态变化回调."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
        for pid, cbs in self._pid_callbacks.items():
            if callback in cbs:
                cbs.remove(callback)

    def start_watching(self) -> None:
        """启动进程监控."""
        if self._watch_thread and self._watch_thread.is_alive():
            raise RuntimeError("进程监视器已启动")

        self._stop_event.clear()
        self._watch_thread = threading.Thread(target=self._watch, daemon=True, name="process-monitor-core")
        self._watch_thread.start()

    def stop_watching(self) -> None:
        """停止进程监控."""
        self._stop_event.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=2.0)

    def _watch(self) -> None:
        """运行监控循环：轮询所有同名进程，检测新增和退出。"""
        known_pids: set[int] = set()

        while not self._stop_event.is_set():
            try:
                current_pids = self._find_all_pids()

                for pid in known_pids - current_pids:
                    self.last_PID = pid
                    self._dispatch(False, pid)

                for pid in current_pids - known_pids:
                    self.last_PID = pid
                    self._dispatch(True, pid)

                known_pids = current_pids
                self._stop_event.wait(self.check_interval)

            except Exception as e:
                self._logger.exception("进程监控异常，短暂等待后重试", e)
                self._stop_event.wait(5.0)

    def _dispatch(self, is_alive: bool, pid: int) -> None:
        """向通用回调和指定 PID 的回调分发状态变更。"""
        for cb in list(self._callbacks):
            try:
                cb(is_alive, pid)
            except Exception as e:
                self._logger.exception("ProcessMonitor 回调执行失败", e)
        for cb in list(self._pid_callbacks.get(pid, [])):
            try:
                cb(is_alive, pid)
            except Exception as e:
                self._logger.exception("ProcessMonitor 回调执行失败", e)

    def _find_all_pids(self) -> set[int]:
        """查找所有同名进程的 PID。"""
        pids: set[int] = set()
        for proc in self._process_service.find_processes(self.process_name):
            pids.add(proc.pid)
        return pids

    def notify_exit(self, pid: int) -> None:
        """直接通知指定 PID 已退出，绕过轮询延迟。"""
        self._dispatch(False, pid)


def _atexit_cleanup() -> None:
    """执行退出清理."""
    if _should_reap:
        for manager in list(_active_managers):
            manager._reap_popen()


atexit.register(_atexit_cleanup)
