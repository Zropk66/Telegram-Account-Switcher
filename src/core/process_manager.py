import asyncio
import atexit
import ctypes
import subprocess
import threading
import time
from contextlib import suppress, contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import Generator, Optional

import psutil

from src.core.config import ConfigService
from src.core.event_bus import (
    Event,
    ProcessStatusChanged,
    event_bus,
    PROCESS_STATUS_CHANGED,
)
from src.core.exceptions import TASException
from src.core.logger import Logger

# Windows API 常量
_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 0x00000102
_WAIT_FAILED = 0xFFFFFFFF
_INVALID_HANDLE_VALUE = -1

kernel32 = ctypes.windll.kernel32


class ProcessManager:
    """Telegram 客户端进程的启动与终止。"""

    _popen_ref: Optional[subprocess.Popen] = None

    @classmethod
    def _reap_popen(cls) -> None:
        """回收子进程资源，避免僵尸进程。"""
        if cls._popen_ref is not None:
            with suppress(Exception):
                cls._popen_ref.poll()
            cls._popen_ref = None

    @contextmanager
    def locked(self, client_name: str, restart_on_exit: bool = False) -> Generator[None, None, None]:
        """
        进程锁定上下文管理器。

        进入时终止已有进程，退出时可选地重新启动。
        """
        self.kill_process(client_name)
        try:
            yield
        finally:
            if restart_on_exit:
                self.start_process(wait=False)

    @staticmethod
    def start_process(wait: bool = True):
        """启动 Telegram 客户端，``wait=True`` 时阻塞等待进程就绪（最多 15 秒）。"""
        configs = ConfigService()
        try:
            full_path = Path(configs.path) / configs.client

            ProcessManager._reap_popen()

            if not wait:
                proc = subprocess.Popen(
                    args=str(full_path),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    shell=False,
                    start_new_session=True,
                )
                ProcessManager._popen_ref = proc
                return True

            # 先订阅事件，再启动进程，防止错过状态通知
            max_time = 15
            ready_event = threading.Event()

            def on_process_status(payload: ProcessStatusChanged):
                if payload.is_alive:
                    ready_event.set()

            event_bus.subscribe(PROCESS_STATUS_CHANGED, on_process_status)
            try:
                proc = subprocess.Popen(
                    args=str(full_path),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    shell=False,
                    start_new_session=True,
                )
                ProcessManager._popen_ref = proc

                success = ready_event.wait(timeout=max_time)
            finally:
                event_bus.unsubscribe(PROCESS_STATUS_CHANGED, on_process_status)

            return success

        except (FileNotFoundError, TypeError, PermissionError):
            return False

    @staticmethod
    def kill_process(client: str):
        """终止所有同名进程，权限不足时抛出异常。"""
        ProcessManager._reap_popen()

        if not isinstance(client, str):
            raise TypeError(f"{client} 必须为 {str}, 但实际为 {type(client)}")

        killed = False
        processes_to_kill = []
        access_denied = False

        for process in psutil.process_iter(['name']):
            if client == process.info.get('name'):
                processes_to_kill.append(process)

        if not processes_to_kill:
            return False

        for process in processes_to_kill:
            try:
                process.terminate()
                killed = True
            except psutil.AccessDenied:
                access_denied = True
            except psutil.NoSuchProcess:
                continue

        gone, alive = psutil.wait_procs(processes_to_kill, timeout=3)
        if alive:
            for p in alive:
                try:
                    p.kill()
                except psutil.AccessDenied:
                    access_denied = True
                except psutil.NoSuchProcess:
                    pass

        if access_denied and not killed:
            raise TASException(
                f"无法终止进程 {client}。由于权限不足，请尝试以管理员身份运行程序。"
            )

        return killed


class ProcessMonitor:
    """
    基于 Windows 事件驱动的进程监控。

    进程存活时用 ``WaitForSingleObject`` 阻塞等待，几乎零 CPU 开销；
    进程不存在时短暂轮询，等待它重新出现。
    状态变化通过 EventBus 广播。
    """

    def __init__(self, process_name: str, *, check_interval: float = 0.5):
        self.process_name = process_name
        self.check_interval = check_interval
        self._watch_task = None
        self.logger = Logger()
        self.last_PID = None

    async def start_watching(self):
        """启动异步监控循环。"""
        if self._watch_task and not self._watch_task.done():
            raise RuntimeError("监视器已启动")

        self._watch_task = asyncio.create_task(self._watch())

    async def stop_watching(self):
        """取消监控任务并等待退出。"""
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._watch_task

    async def _watch(self):
        """监控主循环，状态变化时发布事件。"""
        last_status = None
        loop = asyncio.get_running_loop()

        while True:
            try:
                current_status = await loop.run_in_executor(
                    None, self._wait_for_process_change, last_status
                )

                if current_status != last_status:
                    event_bus.publish(Event(
                        PROCESS_STATUS_CHANGED,
                        ProcessStatusChanged(
                            is_alive=current_status,
                            pid=self.last_PID,
                        ),
                    ))
                    last_status = current_status

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.exception(f"监控错误", e)
                await asyncio.sleep(5)

    def _wait_for_process_change(self, last_status: bool) -> bool:
        """
        在工作线程中阻塞等待进程状态变化。

        - 进程在跑 → ``WaitForSingleObject`` 等它退出
        - 进程不在 → 轮询等它启动
        """
        # 进程正在运行，等它退出
        if last_status and self.last_PID:
            handle = kernel32.OpenProcess(
                wintypes.DWORD(_SYNCHRONIZE),
                wintypes.BOOL(False),
                wintypes.DWORD(self.last_PID),
            )
            if handle and handle != _INVALID_HANDLE_VALUE:
                try:
                    # 超时 1 秒，让主循环有机会检查 CancelledError
                    result = kernel32.WaitForSingleObject(handle, wintypes.DWORD(1000))
                    if result == _WAIT_OBJECT_0:
                        self.last_PID = None
                        return False
                    elif result == _WAIT_TIMEOUT:
                        return True
                    # WAIT_FAILED：句柄可能失效，走下面的重新查找
                finally:
                    kernel32.CloseHandle(handle)

        # 进程不存在，轮询等它启动
        pid = self._find_process_id()
        if pid is not None:
            self.last_PID = pid
            return True

        time.sleep(self.check_interval)
        return False

    def _find_process_id(self) -> Optional[int]:
        """查找目标进程 PID，优先复用上次已知的 PID。"""
        try:
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                if self.last_PID:
                    process = psutil.Process(self.last_PID)
                    if process.is_running() and process.name() == self.process_name:
                        return self.last_PID

            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    if proc.info.get('name') == self.process_name:
                        return proc.pid
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            self.logger.exception(f"查找进程时出现错误", e)
        return None


# 程序退出时自动清理，防止僵尸进程
atexit.register(ProcessManager._reap_popen)
