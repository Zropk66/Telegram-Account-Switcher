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
    recovery,
    Logger,
)
from src.modules.cli_controller import CLIController
from src.modules.config import (
    ConfigService,
    ConfigData,
)
from src.modules.config.key_manager import TelegramKeyManager
from src.modules.logger import set_popup_handler, set_config_provider
from src.ui.adapters import create_cli_callbacks, create_popup_handler
from src.ui.settings_ui import open_settings_window
from src.ui.popup import Popup

# ========== 全局变量 ==========
logger: Logger
CONFIG: ConfigService
TITLE = "TAS"
VERSION = "1.3.0"


def setup_dependency_injection():
    """
    设置依赖注入
    """
    global logger

    # 1. 注入配置提供者到 Logger
    config_provider = ConfigData.as_provider()
    set_config_provider(config_provider)

    def config_log_handler(message: str) -> None:
        if logger:
            logger.error(message)

    ConfigService.set_log_handler(config_log_handler)

    def key_manager_log_handler(message: str) -> None:
        if logger:
            logger.error(message)

    TelegramKeyManager.set_log_handler(key_manager_log_handler)


def create_logger_with_popup() -> Logger:
    """创建带弹窗功能的Logger"""
    new_logger = Logger()
    popup_handler = create_popup_handler()
    set_popup_handler(popup_handler)
    return new_logger


def create_cli_controller(version: str) -> CLIController:
    """创建CLIController"""
    callbacks = create_cli_callbacks()
    return CLIController(
        version=version,
        help_handler=callbacks["help_handler"],
        settings_handler=callbacks["settings_handler"],
        info_handler=callbacks["info_handler"],
        warning_handler=callbacks["warning_handler"],
        error_handler=callbacks["error_handler"],
    )


class TASApp:
    """TAS 应用程序生命周期管理器"""

    def __init__(self, version: str):
        from PySide6.QtWidgets import QApplication
        self.version = version
        self.monitor = None
        self.loop = None
        self._monitor_thread = None
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.ui_controller = Popup.instance()
        self.cli_controller = create_cli_controller(version)

    def __enter__(self):
        global _cleanup_done
        _cleanup_done = False
        register_signal_handlers()
        sys.excepthook = handle_global_exception
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._join_monitor_thread(timeout=5)
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
        self._monitor_thread = threading.Thread(
            target=run_async_in_thread,
            args=(self.loop, self._watcher_task()),
            daemon=True
        )
        self._monitor_thread.name = "process-monitor"
        self._monitor_thread.start()

    def _join_monitor_thread(self, timeout: float = 5):
        """等待监控线程自然退出，超时则强制关闭事件循环"""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=timeout)
            if self._monitor_thread.is_alive() and self.loop is not None and not self.loop.is_closed():
                try:
                    self.loop.call_soon_threadsafe(self.loop.stop)
                except RuntimeError:
                    pass
        self.loop = None

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
            with Popup.context():
                Popup.confirm(msg, "账户切换确认")
            return

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
    config = ConfigService()
    with suppress(Exception):
        if mark:
            _cleanup_done = True
            atexit.unregister(log_and_exit)
            recovery()

        if config.log_output and config.start_time and logger:
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
    if logger:
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
    except RuntimeError:
        pass
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()


def main():
    """主入口"""
    global logger, CONFIG

    setup_dependency_injection()

    logger = create_logger_with_popup()
    CONFIG = ConfigService()

    with TASApp(VERSION) as app:
        return app.run()
