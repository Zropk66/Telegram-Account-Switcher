# -*- coding: utf-8 -*-
import asyncio
import atexit
import ctypes
import subprocess
import time
from contextlib import suppress, contextmanager
from pathlib import Path
from typing import Callable, Generator, Optional

import psutil
from ctypes import wintypes

from src.modules.config import ConfigService
from src.modules.exceptions import TASException
from src.modules.logger import Logger

# Windows API 常量
_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 0x00000102
_WAIT_FAILED = 0xFFFFFFFF
_INVALID_HANDLE_VALUE = -1

kernel32 = ctypes.windll.kernel32


class ProcessManager:
    _popen_ref: Optional[subprocess.Popen] = None

    @classmethod
    def _reap_popen(cls) -> None:
        """清理 Popen 引用，防止僵尸进程"""
        if cls._popen_ref is not None:
            with suppress(Exception):
                cls._popen_ref.poll()  # 回收子进程资源
            cls._popen_ref = None

    @contextmanager
    def locked(self, client_name: str, restart_on_exit: bool = False) -> Generator[None, None, None]:
        """
        进程锁定上下文管理器。
        """
        self.kill_process(client_name)
        try:
            yield
        finally:
            if restart_on_exit:
                self.start_process(wait=False)

    @staticmethod
    def start_process(wait: bool = True):
        """启动客户端"""
        configs = ConfigService()
        try:
            full_path = Path(configs.path) / configs.client

            ProcessManager._reap_popen()

            proc = subprocess.Popen(
                args=str(full_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                shell=False,
                start_new_session=True,
            )
            ProcessManager._popen_ref = proc

            if not wait:
                return True

            max_time = 15
            interval = 0.2
            start_time = time.monotonic()

            while not configs.process_status:
                if time.monotonic() - start_time > max_time:
                    return False
                time.sleep(interval)

            return configs.process_status

        except (FileNotFoundError, TypeError, PermissionError):
            return False

    @staticmethod
    def kill_process(client: str):
        """终止所有匹配的进程"""
        # 清理 Popen 引用
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
    使用 Windows 事件驱动的进程监控。

    进程运行时通过 WaitForSingleObject 阻塞等待进程退出，零 CPU 开销；
    进程不存在时短暂轮询等待进程启动。
    """

    def __init__(self, process_name: str, *, check_interval: float = 0.5):
        self.process_name = process_name
        self._callbacks = []
        self.check_interval = check_interval
        self._watch_task = None
        self.logger = Logger()
        self.last_PID = None

    def add_callback(self, callback: Callable):
        """添加状态变化回调函数"""
        if not callable(callback):
            raise TypeError("回调必须可调用")
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        """移除回调函数"""
        with suppress(ValueError):
            self._callbacks.remove(callback)

    async def start_watching(self):
        """启动监控任务"""
        if self._watch_task and not self._watch_task.done():
            raise RuntimeError("监视器已启动")

        self._watch_task = asyncio.create_task(self._watch())

    async def stop_watching(self):
        """停止监控任务"""
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._watch_task

    async def _watch(self):
        """监控主循环 —— 事件驱动"""
        last_status = None
        loop = asyncio.get_running_loop()

        while True:
            try:
                # 在线程池中执行阻塞的进程查找与等待
                current_status = await loop.run_in_executor(
                    None, self._wait_for_process_change, last_status
                )

                if current_status != last_status:
                    for callback in self._callbacks:
                        try:
                            asyncio.create_task(callback(current_status))
                        except Exception as e:
                            self.logger.exception(f"回调执行失败", e)
                    last_status = current_status

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.exception(f"监控错误", e)
                await asyncio.sleep(5)

    def _wait_for_process_change(self, last_status: bool) -> bool:
        """
        在工作线程中执行：查找进程并事件驱动等待状态变化。

        - 进程运行中 → WaitForSingleObject 阻塞直到退出（事件驱动）
        - 进程不存在 → 短暂轮询等待进程启动
        返回当前进程存活状态。
        """
        # ---- 进程正在运行，等待它退出 ----
        if last_status and self.last_PID:
            handle = kernel32.OpenProcess(
                wintypes.DWORD(_SYNCHRONIZE),
                wintypes.BOOL(False),
                wintypes.DWORD(self.last_PID),
            )
            if handle and handle != _INVALID_HANDLE_VALUE:
                try:
                    # 事件驱动等待：进程退出时立即返回 WAIT_OBJECT_0
                    # 超时 1 秒用于让主循环有机会检查 CancelledError
                    result = kernel32.WaitForSingleObject(handle, wintypes.DWORD(1000))
                    if result == _WAIT_OBJECT_0:
                        self.last_PID = None
                        return False  # 进程已退出
                    elif result == _WAIT_TIMEOUT:
                        return True  # 进程仍在运行，返回让主循环检查取消
                    # WAIT_FAILED 或其他：句柄可能失效，走下面的重新查找逻辑
                finally:
                    kernel32.CloseHandle(handle)

        # ---- 进程不存在或句柄失效，轮询等待进程启动 ----
        pid = self._find_process_id()
        if pid is not None:
            self.last_PID = pid
            return True  # 进程已启动

        # 进程仍未出现，短暂休眠后返回 False
        time.sleep(self.check_interval)
        return False

    def _find_process_id(self) -> Optional[int]:
        """查找目标进程的 PID，优先复用 last_PID"""
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


# 注册退出时清理 Popen 引用，防止僵尸进程
atexit.register(ProcessManager._reap_popen)
