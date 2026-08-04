"""进程管理."""

import atexit
import subprocess
import threading
import weakref
from contextlib import contextmanager, suppress
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

        self._logger.debug(f"使用 hook 模式启动: {full_path}")

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

            self._logger.debug(f"hook 注入成功，PID={pid}")
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

    def bring_to_foreground(self, target_folder: str) -> None:
        """置顶特定账号的窗口."""
        pid = _hook_process_pool.get(target_folder)
        if not pid:
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32

            def enum_windows_callback(hwnd, extra):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    window_pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                    if window_pid.value == pid and user32.IsWindowVisible(hwnd):
                        user32.ShowWindow(hwnd, 9)
                        user32.SetForegroundWindow(hwnd)
                        return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
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

    def register_callback(self, callback: Callable[[bool, Optional[int]], None]) -> None:
        """注册状态变化回调."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[bool, Optional[int]], None]) -> None:
        """注销状态变化回调."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

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
        """运行监控循环."""
        last_status = None

        while not self._stop_event.is_set():
            try:
                current_status = self._wait_for_process_change(last_status)

                if current_status != last_status:
                    for cb in list(self._callbacks):
                        try:
                            cb(current_status, self.last_PID)
                        except Exception as e:
                            self._logger.exception("ProcessMonitor 回调执行失败", e)
                    last_status = current_status

            except Exception as e:
                self._logger.exception("进程监控异常，短暂等待后重试", e)
                self._stop_event.wait(5.0)

    def _wait_for_process_change(self, last_status: bool) -> bool:
        """检测进程状态改变."""
        if last_status and self.last_PID:
            is_dead = self._process_service.wait_for_process(self.last_PID, timeout=1.0)
            if is_dead:
                self.last_PID = None
                return False
            else:
                self._stop_event.wait(self.check_interval)
                return True

        processes = self._process_service.find_processes(self.process_name)
        if processes:
            self.last_PID = processes[0].pid
            return True

        self._stop_event.wait(self.check_interval)
        return False


def _atexit_cleanup() -> None:
    """执行退出清理."""
    if _should_reap:
        for manager in list(_active_managers):
            manager._reap_popen()


atexit.register(_atexit_cleanup)
