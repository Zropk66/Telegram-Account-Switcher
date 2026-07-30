"""Telegram 账户切换器主入口."""

import signal
import sys
import threading
from contextlib import suppress
from pathlib import Path
from types import FrameType, TracebackType
from typing import Optional, Type

from src.core import (
    AccountSwitcher,
    Logger,
    ProcessMonitor,
    recovery,
)
from src.core.cli_controller import CLIAction, CLIController
from src.core.config import (
    ConfigData,
    ConfigService,
)
from src.core.config.key_manager import TelegramKeyManager
from src.core.constants import APP_TITLE, APP_VERSION
from src.core.logger import set_config_provider, set_popup_handler
from src.core.single_instance import SingleInstanceException, SingleInstanceLock
from src.ui.adapters import create_popup_handler
from src.ui.popup import Popup

logger: Logger
CONFIG: ConfigService

TITLE = APP_TITLE
VERSION = APP_VERSION


def setup_dependency_injection() -> None:
    """配置依赖注入."""
    global logger

    config_provider = ConfigData.as_provider()
    set_config_provider(config_provider)

    def config_log_handler(message: str) -> None:
        """记录配置日志."""
        if logger:
            logger.error(message)

    ConfigService.set_log_handler(config_log_handler)

    def key_manager_log_handler(message: str) -> None:
        """记录密钥管理器日志."""
        if logger:
            logger.error(message)

    TelegramKeyManager.set_log_handler(key_manager_log_handler)


def create_logger_with_popup() -> Logger:
    """创建带弹窗的日志记录器."""
    new_logger = Logger()
    popup_handler = create_popup_handler()
    set_popup_handler(popup_handler)
    return new_logger


class TASApp:
    """账户切换应用程序."""

    def __init__(self, version: str) -> None:
        """初始化应用程序."""
        from PySide6.QtWidgets import QApplication

        self.version = version
        self.monitor = None
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.ui_controller = Popup.instance()
        self.cli_controller = CLIController(version=version)

    def __enter__(self) -> "TASApp":
        """进入上下文管理器."""
        global _cleanup_done
        _cleanup_done.clear()
        register_signal_handlers()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """退出上下文管理器."""
        if self.monitor:
            self.monitor.stop_watching()
        log_and_exit(mark=True)

    def run(self) -> int:
        """运行应用程序."""
        try:
            args = self.cli_controller.parse_args()
            Logger.set_debug(getattr(args, "debug", False))
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:
            if logger:
                logger.error(f"参数解析失败: {e}")
            return 1

        config_file = Path(CONFIG.config_file)
        if not config_file.exists() or not self.cli_controller.check_config(args):
            from src.ui.settings_ui import open_settings_window

            open_settings_window(self.version)
            return 0

        action = self.cli_controller.handle_actions(args)

        if action == CLIAction.SHOW_HELP:
            from src.ui.help_ui import open_help_window

            open_help_window(self.version)
            return 0
        elif action == CLIAction.SHOW_SETTINGS:
            from src.ui.settings_ui import open_settings_window

            open_settings_window(self.version)
            return 0
        elif action == CLIAction.EXIT:
            return 0

        logger.info(f"切换账户: {CONFIG.tag or CONFIG.default}")
        logger.debug(f"Telegram路径: {CONFIG.path}")

        def wrapped_confirm(msg: str) -> bool:
            """确认切换账户."""
            with Popup.context():
                return Popup.confirm(msg, "账户切换确认")

        switcher = AccountSwitcher()
        switched = switcher.process(confirm_callback=wrapped_confirm)
        if not switched:
            logger.error("账户切换失败")
            return 1

        account_monitor = switcher.monitor
        if account_monitor:
            logger.debug("账户切换成功，开始后台监控")
            self.monitor = ProcessMonitor(CONFIG.client, logger=logger)
            with self.monitor.watch(account_monitor.handle_process_status):
                account_monitor.run()

        return 0


_cleanup_done = threading.Event()


def log_and_exit(mark: bool = False) -> None:
    """记录日志并退出."""
    global _cleanup_done, CONFIG
    if mark and _cleanup_done.is_set():
        return None
    with suppress(Exception):
        if mark:
            _cleanup_done.set()
            recovery(config=CONFIG, logger=logger)

        if CONFIG:
            CONFIG.shutdown()
            if CONFIG.log_output and CONFIG.start_time and logger:
                logger.info(f"运行时长：{CONFIG.watch_time()}")
    return None


def register_signal_handlers() -> None:
    """注册信号处理器."""

    def handle_interrupt(signum: int, frame: Optional[FrameType]) -> None:
        """处理中断信号."""
        log_and_exit(True)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_interrupt)


def handle_global_exception(
    exc_type: Type[BaseException],
    exc_value: BaseException,
    exc_traceback: Optional[TracebackType],
) -> None:
    """处理全局异常."""
    if exc_type in (KeyboardInterrupt, SystemExit):
        sys.exit(0)

    if logger:
        logger.exception(
            "捕获到未处理异常, 请尝试重启程序或联系开发者.",
            exc_value,
            popup=True,
        )
        return

    import ctypes
    import traceback

    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    error_msg = f"捕获到未处理异常, 请尝试重启程序或联系开发者.\n\n{tb_text}"
    ctypes.windll.user32.MessageBoxW(0, error_msg, "TAS - 未处理异常", 0x10)


def main() -> int:
    """程序主入口."""
    sys.excepthook = handle_global_exception
    try:
        with SingleInstanceLock.ensure_single_instance():
            global logger, CONFIG

            setup_dependency_injection()
            logger = create_logger_with_popup()
            CONFIG = ConfigService()

            logger.info("初始化成功")

            try:
                with TASApp(VERSION) as app:
                    return app.run()
            except KeyboardInterrupt:
                return 0
            except Exception as e:
                logger.exception("程序异常终止", e)
                return 1
    except SingleInstanceException as e:
        with Popup.context():
            Popup.alert(str(e), "客户端重复启动")
        return 1
