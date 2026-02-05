# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import subprocess
import time
from contextlib import suppress
from pathlib import Path
from typing import Callable
import asyncio
import psutil

from src.modules import ConfigManage
from src.modules.exceptions import TASException
from src.modules.logger import Logger


class ProcessManager:
    @staticmethod
    def start_process(configs: ConfigManage):
        """客户端启动函数"""
        try:
            full_path = Path(configs.path) / configs.client

            subprocess.Popen(
                args=str(full_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                shell=False,
                start_new_session=True,
            )

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
        if not isinstance(client, str):
            raise TypeError(f"{client} 必须为 {str}, 但实际为 {type(client)}")

        killed = False
        processes_to_kill = []
        access_denied = False

        for process in psutil.process_iter(['name']):
            if client == process.info['name']:
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
                f"无法终止进程 {client}。权限不足，请尝试以管理员身份运行程序。"
            )

        return killed


class ProcessMonitor:
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
            raise TypeError("回调函数必须可调用")
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
        """监控主循环"""
        last_status = None
        while True:
            try:
                current_status = await self._check_status()

                if current_status != last_status:
                    for callback in self._callbacks:
                        try:
                            asyncio.create_task(callback(current_status))
                        except Exception as e:
                            self.logger.exception(f"函数回调失败.", e)
                    last_status = current_status

                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.exception(f"监控错误", e)
                await asyncio.sleep(5)

    async def _check_status(self) -> bool:
        """检查进程状态"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._status_checker, self.process_name)

    def _status_checker(self, process_name: str) -> bool:
        """进程状态检查器"""
        try:
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                if self.last_PID:
                    process = psutil.Process(self.last_PID)
                    if process.is_running() and process.name() == process_name:
                        return True

            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    proc_name = proc.info.get('name')
                    if proc_name == process_name:
                        self.last_PID = proc.pid
                        return True
                except (
                        psutil.NoSuchProcess,
                        psutil.AccessDenied,
                        psutil.ZombieProcess,
                ):
                    continue
            return False
        except Exception as e:
            self.logger.exception(f"检查进程状态时出现错误.", e)
            return False
