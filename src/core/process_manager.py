"""
进程管理。
"""
import atexit
import subprocess
import threading
import weakref
from contextlib import suppress, contextmanager
from pathlib import Path
from typing import Generator, Optional, Callable

from src.core.config import ConfigService
from src.core.exceptions import TASException
from src.core.logger import Logger
from src.core.process_service import PsutilProcessService
from src.core.runtime import delay

_should_reap: bool = True
_active_managers = weakref.WeakSet()


def _set_should_reap(value: bool) -> None:
    """设置是否释放句柄。"""
    global _should_reap
    _should_reap = value


class ProcessManager:
    """进程管理器。"""

    def __init__(self, process_service: Optional[PsutilProcessService] = None, config: Optional[ConfigService] = None,
                 logger: Optional[Logger] = None):
        """初始化进程管理器。"""
        self._popen_ref: Optional[subprocess.Popen] = None
        self._process_service = process_service or PsutilProcessService()
        self._config = config or ConfigService()
        self._logger = logger or Logger()
        _active_managers.add(self)

    def _reap_popen(self) -> None:
        """释放子进程资源。"""
        if not _should_reap:
            return
        if self._popen_ref is not None:
            with suppress(Exception):
                self._popen_ref.poll()
            self._popen_ref = None

    @contextmanager
    def kill_and_guard(self, client_name: str, restart_on_exit: bool = False) -> Generator[None, None, None]:
        """关闭并防护进程。"""
        self.kill_process(client_name)
        try:
            yield
        finally:
            if restart_on_exit:
                self.start_process(wait=False)

    def start_process(self, wait: bool = True) -> bool:
        """启动客户端进程。"""
        try:
            full_path = Path(self._config.path) / self._config.client

            if not full_path.exists():
                self._logger.error(f"找不到客户端可执行文件: {full_path}")
                return False

            self._reap_popen()

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

            max_time = 15
            poll_interval = 0.1
            elapsed = 0.0
            success = False

            while elapsed < max_time:
                if self._process_service.find_processes(self._config.client):
                    success = True
                    break
                delay(poll_interval)
                elapsed += poll_interval

            if not success:
                self._logger.warning(f"等待进程启动超时 ({max_time}s)")

            return success

        except (FileNotFoundError, PermissionError) as e:
            self._logger.error(f"启动失败: {e}")
            return False
        except Exception as e:
            self._logger.error(f"启动过程出现未预期错误: {e}")
            return False

    def kill_process(self, client: str):
        """杀死指定客户端进程。"""
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
            raise TASException(f"权限不足，无法终止进程: {client}。请手动关闭或以管理员身份运行。")

        return killed


class ProcessMonitor:
    """进程状态监视器。"""

    def __init__(
            self,
            process_name: str,
            *,
            check_interval: float = 0.5,
            test_mode: bool = False,
            logger: Optional[Logger] = None,
            process_service: Optional[PsutilProcessService] = None,
    ):
        """初始化进程监视器。"""
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
    def watch(self, callback: Callable[[bool, Optional[int]], None]):
        """管理监控生命周期。"""
        self.register_callback(callback)
        self.start_watching()
        try:
            yield self
        finally:
            self.unregister_callback(callback)
            self.stop_watching()

    def register_callback(self, callback: Callable[[bool, Optional[int]], None]) -> None:
        """注册状态变化回调。"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[bool, Optional[int]], None]) -> None:
        """注销状态变化回调。"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def start_watching(self):
        """启动进程监控。"""
        if self._watch_thread and self._watch_thread.is_alive():
            raise RuntimeError("进程监视器已启动")

        self._stop_event.clear()
        self._watch_thread = threading.Thread(target=self._watch, daemon=True, name="process-monitor-core")
        self._watch_thread.start()

    def stop_watching(self):
        """停止进程监控。"""
        self._stop_event.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=2.0)

    def _watch(self):
        """运行监控循环。"""
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
                self._logger.exception(f"进程监控异常，短暂等待后重试", e)
                self._stop_event.wait(5.0)

    def _wait_for_process_change(self, last_status: bool) -> bool:
        """检测进程状态改变。"""
        if last_status and self.last_PID:
            is_dead = self._process_service.wait_for_process(self.last_PID, timeout=1.0)
            if is_dead:
                self.last_PID = None
                return False
            else:
                return True

        processes = self._process_service.find_processes(self.process_name)
        if processes:
            self.last_PID = processes[0].pid
            return True

        self._stop_event.wait(self.check_interval)
        return False


def _atexit_cleanup():
    """执行退出清理。"""
    if _should_reap:
        for manager in list(_active_managers):
            manager._reap_popen()


atexit.register(_atexit_cleanup)