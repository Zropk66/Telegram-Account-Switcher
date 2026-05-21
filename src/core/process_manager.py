"""
Telegram 客户端进程管理。

封装了进程的启动、终止和监控逻辑。使用后台线程进行低功耗监控，
并支持进程状态的全局事件通知。
"""
import atexit
import subprocess
import threading
from contextlib import suppress, contextmanager
from pathlib import Path
from typing import Generator, Optional, Callable

import psutil

from src.core.config import ConfigService
from src.core.exceptions import TASException
from src.core.logger import Logger
from src.core.process_service import PsutilProcessService
from src.core.runtime import delay

# 内部标志：决定在主程序退出时是否需要清理通过 Popen 启动的子进程
_should_reap: bool = True


def _set_should_reap(value: bool) -> None:
    """内部测试或特殊场景下禁用自动资源回收。"""
    global _should_reap
    _should_reap = value


class ProcessManager:
    """
    进程控制器。

    协调 Telegram 的生命周期，支持优雅关闭、强制清理以及启动后的就绪检测。
    """

    def __init__(self, process_service: Optional[PsutilProcessService] = None, config: Optional[ConfigService] = None,
                 logger: Optional[Logger] = None):
        """
        初始化管理器。

        可以通过注入 process_service 来改变底层的进程操作实现（如单元测试中的 Mock）。
        """
        self._popen_ref: Optional[subprocess.Popen] = None
        self._process_service = process_service or PsutilProcessService()
        self._config = config or ConfigService()
        self._logger = logger or Logger()

    def _reap_popen(self) -> None:
        """调用 poll() 回收子进程，防止父进程退出前产生僵尸进程。"""
        if not _should_reap:
            return
        if self._popen_ref is not None:
            with suppress(Exception):
                self._popen_ref.poll()
            self._popen_ref = None

    @contextmanager
    def kill_and_guard(self, client_name: str, restart_on_exit: bool = False) -> Generator[None, None, None]:
        """
        进程安全防护上下文。

        进入时确保清理掉现有的 Telegram 进程，常用于文件交换等需要独占访问的场景。
        """
        self.kill_process(client_name)
        try:
            yield
        finally:
            if restart_on_exit:
                self.start_process(wait=False)

    def start_process(self, wait: bool = True) -> bool:
        """
        启动 Telegram。

        wait=True 时会阻塞轮询，直到检测到进程已运行或达到 15s 超时。
        """
        try:
            full_path = Path(self._config.path) / self._config.client

            if not full_path.exists():
                self._logger.error(f"找不到客户端可执行文件: {full_path}")
                return False

            self._reap_popen()

            # 仅启动不等待，用于退出时的快速重启
            if not wait:
                self._logger.debug(f"启动进程: {full_path}")
                proc = subprocess.Popen(
                    args=str(full_path),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    shell=False,
                    start_new_session=True,
                )
                self._popen_ref = proc
                return True

            # 阻塞启动：需要等待进程真正运行起来
            self._logger.debug(f"启动并等待就绪: {full_path}")
            proc = subprocess.Popen(
                args=str(full_path),
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
        """
        清理 Telegram 进程。

        逻辑：先尝试 SIGTERM (terminate)，如果没用再调用 kill。
        如果清理后进程依然存在，则认为权限不足，抛出异常阻断后续操作。
        """
        self._reap_popen()

        if not isinstance(client, str):
            raise TypeError(f"client 名称必须是字符串，实际为 {type(client)}")

        killed = False
        processes_to_kill = self._process_service.find_processes(client)

        if not processes_to_kill:
            return False

        self._logger.debug(f"正在清理 {len(processes_to_kill)} 个 {client} 进程...")

        # 1. 尝试优雅退出
        for proc_info in processes_to_kill:
            if self._process_service.terminate(proc_info.pid):
                killed = True

        # 给系统一点处理信号的时间
        delay(0.1)

        # 2. 检查残留并强制结束
        remaining = self._process_service.find_processes(client)
        for proc_info in remaining:
            if self._process_service.kill(proc_info.pid):
                killed = True

        # 3. 最终校验：如果清理后还能查到进程，说明权限不够或者进程卡死
        if self._process_service.find_processes(client):
            raise TASException(f"权限不足，无法终止进程: {client}。请手动关闭或以管理员身份运行。")

        return killed


class ProcessMonitor:
    """
    高效的进程监视器。

    核心逻辑是在独立线程中轮询及等待进程状态变更。
    """

    def __init__(
            self,
            process_name: str,
            *,
            check_interval: float = 0.5,
            test_mode: bool = False,
            logger: Optional[Logger] = None,
            process_service: Optional[PsutilProcessService] = None,
    ):
        """初始化。"""
        self.process_name = process_name
        self.check_interval = check_interval
        self._watch_thread = None
        self._stop_event = threading.Event()
        self._logger = logger or Logger()
        self._process_service = process_service or PsutilProcessService()
        self.last_PID = None
        self._test_mode = test_mode
        self._callbacks: list[Callable[[bool, Optional[int]], None]] = []

    def register_callback(self, callback: Callable[[bool, Optional[int]], None]) -> None:
        """注册状态变更回调。"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[bool, Optional[int]], None]) -> None:
        """移除状态变更回调。"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def start_watching(self):
        """进入后台监视循环。"""
        if self._watch_thread and self._watch_thread.is_alive():
            raise RuntimeError("进程监视器已启动")

        self._stop_event.clear()
        self._watch_thread = threading.Thread(target=self._watch, daemon=True, name="process-monitor-core")
        self._watch_thread.start()

    def stop_watching(self):
        """取消监视任务并等待结束。"""
        self._stop_event.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=2.0)

    def _watch(self):
        """主监控循环，状态变化时触发回调。"""
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
        """
        阻塞等待状态变更的核心方法。
        """
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
    """注册 atexit 钩子，确保程序退出时清理可能残留的子进程引用。"""
    if _should_reap:
        from src.core.process_manager import ProcessManager
        ProcessManager()._reap_popen()


atexit.register(_atexit_cleanup)