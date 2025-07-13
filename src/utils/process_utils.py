# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import asyncio
from contextlib import suppress
from typing import Callable

import psutil

from src.utils.exceptions import TASException
from src.utils.logger import Logger


def try_kill_process(client: str):
    if not isinstance(client, str):
        raise TypeError(f"{client} 必须为 {str}, 但实际为 {type(client)}")
    for process in psutil.process_iter(['name']):
        process_name = process.info['name']
        if client == process_name:
            try:
                process.terminate()
                return True
            except psutil.NoSuchProcess:
                return True
            except (PermissionError, psutil.AccessDenied) as e:
                raise TASException(f'终止进程 {process_name} 的操作失败') from e
    return False


class ProcessWatcher:
    def __init__(self, process_name: str, *, check_interval: float = 1.0, ):
        self.process_name = process_name
        self._callbacks = []
        self.check_interval = check_interval
        self._watch_task = None
        self.logger = Logger()
        self.last_PID = None

    def add_callback(self, callback):
        """添加状态变化回调函数"""
        if not callable(callback):
            raise TypeError("回调函数必须可调用")
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[bool], None]):
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
            try:
                process = psutil.Process(self.last_PID)
                if process and process.name() == process_name:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    if process_name in proc.info['name']:
                        self.last_PID = proc.pid
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            return False
        except Exception as e:
            self.logger.exception(f"检查进程状态时出现错误.", e)
            return False
