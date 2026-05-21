"""
Telegram 账户切换器主入口。

负责初始化全局依赖、处理命令行入口、启动进程监控，并驱动一次账户切换流程。
"""
import signal
import sys
import threading
from contextlib import suppress
from pathlib import Path

from src.core import (
    AccountSwitcher,
    ProcessMonitor,
    recovery,
    Logger,
)
from src.core.cli_controller import CLIController
from src.core.config import (
    ConfigService,
    ConfigData,
)
from src.core.config.key_manager import TelegramKeyManager
from src.core.logger import set_popup_handler, set_config_provider
from src.core.single_instance import SingleInstanceLock, SingleInstanceException
from src.ui.adapters import create_cli_callbacks, create_popup_handler
from src.ui.popup import Popup
from src.ui.settings_ui import open_settings_window

logger: Logger
CONFIG: ConfigService

TITLE = "TAS"
VERSION = "2.0.0"


def setup_dependency_injection():
    """把配置和日志回调注入到仍需全局访问的服务中。"""
    global logger

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
    """创建日志器。"""
    new_logger = Logger()
    popup_handler = create_popup_handler()
    set_popup_handler(popup_handler)
    return new_logger


def create_cli_controller(version: str) -> CLIController:
    """构建命令行控制器。"""
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
    """管理一次应用运行周期，从参数解析到切换完成事件。"""

    def __init__(self, version: str):
        from PySide6.QtWidgets import QApplication
        self.version = version
        self.monitor = None
        self._watcher_thread = None
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.ui_controller = Popup.instance()
        self.cli_controller = create_cli_controller(version)

    def __enter__(self):
        """注册退出保护，确保异常和中断都会走统一清理路径。"""
        global _cleanup_done
        _cleanup_done.clear()
        register_signal_handlers()
        sys.excepthook = handle_global_exception
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时等待监控线程结束，并释放单实例锁。"""
        self._join_monitor_thread(timeout=5)
        SingleInstanceLock.cleanup()
        log_and_exit(mark=True)

    def _watcher_task(self, account_monitor):
        """后台监控 Telegram 进程，直到收到应用完成事件。"""
        self.monitor.register_callback(account_monitor.handle_process_status)
        self.monitor.start_watching()

        completion_event = threading.Event()
        account_monitor.register_on_completion(lambda success, msg: completion_event.set())

        try:
            completion_event.wait()
        finally:
            self.monitor.unregister_callback(account_monitor.handle_process_status)
            self.monitor.stop_watching()

    def start_monitoring(self, account_monitor):
        """在独立守护线程中启动监控任务。"""
        self.monitor = ProcessMonitor(CONFIG.client, logger=logger)
        self._watcher_thread = threading.Thread(
            target=self._watcher_task,
            args=(account_monitor,),
            daemon=True
        )
        self._watcher_thread.name = "app-watcher-thread"
        self._watcher_thread.start()

    def _join_monitor_thread(self, timeout: float = 5):
        """等待监控线程退出。"""
        if self.monitor:
            self.monitor.stop_watching()
        if self._watcher_thread is not None and self._watcher_thread.is_alive():
            self._watcher_thread.join(timeout=timeout)

    def run(self):
        """执行 CLI 分支或账户切换主流程，并返回进程退出码。"""
        try:
            args = self.cli_controller.parse_args()
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:
            if logger:
                logger.error(f"参数解析失败: {e}")
            return 1

        config_file = Path(CONFIG.config_file)
        if not config_file.exists() or not self.cli_controller.check_config(args):
            open_settings_window(self.version)
            return 0

        if self.cli_controller.handle_actions(args):
            return 0

        logger.info(f"切换账户: {CONFIG.tag or CONFIG.default}")
        logger.debug(f"Telegram路径: {CONFIG.path}")

        def wrapped_confirm(msg):
            with Popup.context():
                return Popup.confirm(msg, "账户切换确认")

        switcher = AccountSwitcher()
        switched = switcher.process(confirm_callback=wrapped_confirm)
        if not switched:
            logger.error("账户切换失败")
            return 1

        account_monitor = switcher.monitor
        if account_monitor:
            self.start_monitoring(account_monitor)

        logger.debug("账户切换成功，等待完成")
        self._wait_for_completion(account_monitor)
        return 0

    @staticmethod
    def _wait_for_completion(account_monitor):
        """等待账户切换监控完成。"""
        if account_monitor:
            account_monitor.completion_event.wait()


_cleanup_done = threading.Event()


def log_and_exit(mark=False):
    """退出前执行一次性清理，避免重复恢复默认账户。"""
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


def register_signal_handlers():
    """把 Ctrl+C 接入统一清理流程。"""

    def handle_interrupt(signum, frame):
        log_and_exit(True)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_interrupt)


def handle_global_exception(exc_type, exc_value, exc_traceback):
    """记录未处理异常，并在可能时通过弹窗提示用户。"""
    if exc_type in (KeyboardInterrupt, SystemExit):
        sys.exit(0)
    if logger:
        logger.exception(
            "捕获到未处理异常, 请尝试重启程序或联系开发者.",
            exc_value,
            popup=True,
        )


def main():
    """应用程序入口。"""
    try:
        SingleInstanceLock.ensure_single_instance()
    except SingleInstanceException as e:
        with Popup.context():
            Popup.alert(e.message, "客户端重复启动")
        return 1

    global logger, CONFIG

    setup_dependency_injection()
    logger = create_logger_with_popup()
    CONFIG = ConfigService()

    logger.info(f"初始化成功")

    try:
        with TASApp(VERSION) as app:
            return app.run()
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        logger.exception("程序异常终止", e)
        return 1
