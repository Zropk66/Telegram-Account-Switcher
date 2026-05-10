# -*- coding: utf-8 -*-
import asyncio
import atexit
import signal
import sys
import threading
from contextlib import suppress
from pathlib import Path

from src.modules import (
    AccountSwitcher,
    ProcessManager,
    ProcessMonitor,
    ConfigManage,
    recovery,
    Logger,
)
from src.modules.cli_controller import CLIController
from src.ui.settings_ui import open_settings_window
from src.ui.ui_controller import UIController, confirm

logger = Logger()
TITLE = "TAS"
VERSION = "1.3.0"
CONFIG = ConfigManage()

from src.modules.utils import search_file_in_dirs as _search_func

def search_file_in_dirs(path: str, tag: str):
    """搜索账户文件夹"""
    return _search_func(path, tag)

_cli_controller_instance = None


def _get_cli_controller() -> CLIController:
    """获取 CLI 控制器实例"""
    global _cli_controller_instance
    if _cli_controller_instance is None:
        _cli_controller_instance = CLIController(VERSION)
    return _cli_controller_instance


def process_tags(operation: str) -> None:
    """批量处理账户的加解密"""
    return _get_cli_controller()._process_tags(operation)


def process_single_tag(tag: str, operation: str) -> None:
    """处理单个账户的加解密"""
    return _get_cli_controller()._process_single_tag(tag, operation)


def check_configs(args) -> bool:
    """检查配置是否有效"""
    return _get_cli_controller().check_config(args)


def parse_args():
    """解析命令行参数"""
    return _get_cli_controller().parse_args()


def handle_cli_actions(args) -> bool:
    """处理 CLI 动作"""
    return _get_cli_controller().handle_actions(args)


class TASApp:
    """TAS 应用程序生命周期管理器"""

    def __init__(self, version: str):
        from PySide6.QtWidgets import QApplication
        self.version = version
        self.monitor = None
        self.loop = None
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.ui_controller = UIController.instance()
        self.cli_controller = CLIController(version)

    def __enter__(self):
        global _cleanup_done
        _cleanup_done = False
        register_signal_handlers()
        sys.excepthook = handle_global_exception
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        log_and_exit(mark=True)

    async def _watcher_task(self):
        """运行进程健康监控"""
        self.monitor.add_callback(status_handler)
        await self.monitor.start_watching()
        while not CONFIG.complete:
            await asyncio.sleep(1)
        await self.monitor.stop_watching()

    def start_monitoring(self):
        """启动监控线程"""
        self.loop = asyncio.new_event_loop()
        self.monitor = ProcessMonitor(CONFIG.client)
        threading.Thread(
            target=run_async_in_thread,
            args=(self.loop, self._watcher_task()),
            daemon=True
        ).start()
        # logger.info("监控线程启动成功")

    def run(self):
        """运行主逻辑"""
        try:
            args = self.cli_controller.parse_args()
        except Exception:
            return 0

        config_file = Path(CONFIG.config_file)
        if not config_file.exists() or not self.cli_controller.check_config(args):
            open_settings_window(self.version)
            return 0

        if self.cli_controller.handle_actions(args):
            return 0

        logger.info("初始化成功")

        self.start_monitoring()

        ProcessManager.kill_process(CONFIG.client)

        def wrapped_confirm(msg):
            return confirm(msg, "账户切换确认")

        switched = AccountSwitcher().process(confirm_callback=wrapped_confirm)

        if not switched:
            return 1

        self._wait_for_completion()
        return 0

    @staticmethod
    def _wait_for_completion():
        """等待监控完成"""
        import time
        while not CONFIG.complete:
            time.sleep(0.5)


_cleanup_done = False


def log_and_exit(mark=False):
    """程序退出清理"""
    global _cleanup_done
    if mark and _cleanup_done:
        return None
    config = ConfigManage()
    with suppress(Exception):
        if mark:
            _cleanup_done = True
            atexit.unregister(log_and_exit)
            recovery()

        if config.log_output and config.start_time:
            logger.info(f"运行时长：{config.watch_time()}")
    return None


def register_signal_handlers():
    """注册信号监听"""

    def handle_interrupt(signum, frame):
        log_and_exit(True)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_interrupt)


def handle_global_exception(exc_type, exc_value, exc_traceback):
    """全局异常捕获"""
    if exc_type in (KeyboardInterrupt, SystemExit):
        sys.exit(0)
    logger.exception(
        "捕获到未处理异常, 请尝试重启程序或联系开发者.",
        exc_value,
        popup=True,
    )


async def status_handler(is_alive: bool) -> None:
    CONFIG.process_status = is_alive


def run_async_in_thread(loop, coro) -> None:
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


def main():
    """主入口"""
    with TASApp(VERSION) as app:
        return app.run()
