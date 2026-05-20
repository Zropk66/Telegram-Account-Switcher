"""
Telegram 客户端进程管理。

封装了进程的启动、终止和监控逻辑。使用 Windows API 实现低功耗监控，
并支持进程状态的全局事件通知。
"""
import asyncio
import atexit
import ctypes
import subprocess
import threading
from contextlib import suppress, contextmanager
from pathlib import Path
from typing import Generator, Optional

import psutil

from src.core.event_bus import (
    Event,
    ProcessStatusChanged,
    get_event_bus,
    PROCESS_STATUS_CHANGED,
)
from src.core.exceptions import TASException
from src.core.interfaces import IProcessService, IConfigProvider, ILogger
from src.core.logger import Logger
from src.core.runtime import delay

# Windows API 句柄和常量，用于 WaitForSingleObject
_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 0x00000102
_WAIT_FAILED = 0xFFFFFFFF
_INVALID_HANDLE_VALUE = -1

kernel32 = ctypes.windll.kernel32

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

    def __init__(self, process_service: Optional[IProcessService] = None, config: Optional[IConfigProvider] = None,
                 logger: Optional[ILogger] = None):
        """
        初始化管理器。

        可以通过注入 process_service 来改变底层的进程操作实现（如单元测试中的 Mock）。
        """
        from src.core.process_service import PsutilProcessService
        from src.core.config import ConfigService
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

    def start_process(self, wait: bool = True):
        """
        启动 Telegram。

        wait=True 时会订阅事件总线，直到检测到进程已进入 Active 状态或达到 15s 超时。
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
            max_time = 15
            ready_event = threading.Event()

            def on_process_status(payload: ProcessStatusChanged):
                """on_process_status 方法。"""
                if payload.is_alive:
                    ready_event.set()

            get_event_bus().subscribe(PROCESS_STATUS_CHANGED, on_process_status)
            try:
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
                success = ready_event.wait(timeout=max_time)
                if not success:
                    self._logger.warning(f"等待进程启动超时 ({max_time}s)")
            finally:
                get_event_bus().unsubscribe(PROCESS_STATUS_CHANGED, on_process_status)

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

    核心逻辑是在独立线程中调用 Windows 的 WaitForSingleObject。
    这意味着当 Telegram 运行时，监控线程是处于内核级的挂起状态，不占用 CPU 时间片。
    """

    def __init__(
            self,
            process_name: str,
            *,
            check_interval: float = 0.5,
            test_mode: bool = False,
            event_bus=None,
            logger: Optional[ILogger] = None,
    ):
        """初始化。"""
        self.process_name = process_name
        self.check_interval = check_interval
        self._watch_task = None
        self._logger = logger or Logger()
        self.last_PID = None
        self._test_mode = test_mode
        self._event_bus = event_bus or get_event_bus()

    async def start_watching(self):
        """进入后台监视循环。"""
        if self._watch_task and not self._watch_task.done():
            raise RuntimeError("进程监视器已启动")

        self._watch_task = asyncio.create_task(self._watch())

    async def stop_watching(self):
        """取消监视任务并等待结束。"""
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._watch_task

    async def _watch(self):
        """主监控循环，状态变化时通过 EventBus 发布通知。"""
        last_status = None

        while True:
            try:
                current_status = await asyncio.to_thread(self._wait_for_process_change, last_status)

                if current_status != last_status:
                    self._event_bus.publish(Event(
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
                self._logger.exception(f"进程监控异常，5s 后重试", e)
                await asyncio.sleep(5)

    def _wait_for_process_change(self, last_status: bool) -> bool:
        """
        阻塞等待状态变更的核心方法。
        """
        # 情况 A: 进程运行中，调用 Windows API 挂起线程等待信号
        if last_status and self.last_PID:
            handle = kernel32.OpenProcess(_SYNCHRONIZE, False, self.last_PID)
            if handle and handle != _INVALID_HANDLE_VALUE:
                try:
                    # 1秒超时是为了能响应 asyncio 的 CancelledError
                    result = kernel32.WaitForSingleObject(handle, 1000)
                    if result == _WAIT_OBJECT_0:
                        self.last_PID = None
                        return False
                    elif result == _WAIT_TIMEOUT:
                        return True
                finally:
                    kernel32.CloseHandle(handle)

        # 情况 B: 进程未运行，通过 psutil 轮询查找
        pid = self._find_process_id()
        if pid is not None:
            self.last_PID = pid
            return True

        delay(self.check_interval)
        return False

    def _find_process_id(self) -> Optional[int]:
        """定位目标进程 PID，优先校验上次记录的 PID 是否依然匹配。"""
        try:
            # 路径 1: 检查缓存 PID 是否有效且名称一致
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                if self.last_PID:
                    process = psutil.Process(self.last_PID)
                    if process.is_running() and process.name() == self.process_name:
                        return self.last_PID

            # 路径 2: 遍历所有进程寻找匹配项
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    if proc.info.get('name') == self.process_name:
                        return proc.info.get('pid')
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            self._logger.exception(f"遍历进程列表失败", e)
        return None


def _atexit_cleanup():
    """注册 atexit 钩子，确保程序退出时清理可能残留的子进程引用。"""
    if _should_reap:
        from src.core.process_manager import ProcessManager
        ProcessManager()._reap_popen()


atexit.register(_atexit_cleanup)
