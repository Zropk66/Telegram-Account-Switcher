import asyncio
import atexit
import signal
import sys
import threading
from contextlib import suppress
from pathlib import Path

from src.core import (
    AccountSwitcher,
    ProcessManager,
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
from src.core.event_bus import (
    AppCompletionEvent,
    event_bus,
    APP_COMPLETION,
)
from src.core.logger import set_popup_handler, set_config_provider
from src.ui.adapters import create_cli_callbacks, create_popup_handler
from src.ui.popup import Popup
from src.ui.settings_ui import open_settings_window

# -- 全局状态 --
logger: Logger
CONFIG: ConfigService
TITLE = "TAS"
VERSION = "2.0.0"


def setup_dependency_injection():
    """把配置提供者和日志处理器注入到各模块，建立依赖关系。"""
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
    """创建 Logger 实例，并挂载弹窗处理器。"""
    new_logger = Logger()
    popup_handler = create_popup_handler()
    set_popup_handler(popup_handler)
    return new_logger


def create_cli_controller(version: str) -> CLIController:
    """构建 CLIController，注入所有 UI 回调。"""
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
    """管理应用的整体生命周期：初始化 → 切换账户 → 监控 → 退出清理。"""

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
        """在后台持续监控进程状态，直到收到任务完成事件。"""
        await self.monitor.start_watching()
        completion_event = asyncio.Event()

        def on_completion(payload: AppCompletionEvent):
            completion_event.set()

        event_bus.subscribe(APP_COMPLETION, on_completion)
        try:
            await completion_event.wait()
        finally:
            event_bus.unsubscribe(APP_COMPLETION, on_completion)
        await self.monitor.stop_watching()

    def start_monitoring(self):
        """在新线程中启动进程监控。"""
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
        """等监控线程结束，超时就强行关闭事件循环。"""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=timeout)
            if self._monitor_thread.is_alive() and self.loop is not None and not self.loop.is_closed():
                try:
                    self.loop.call_soon_threadsafe(self.loop.stop)
                except RuntimeError:
                    pass
        self.loop = None

    def run(self):
        """应用主流程：解析参数 → 校验配置 → 切换账户 → 等待完成。"""
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
                return Popup.confirm(msg, "账户切换确认")

        switched = AccountSwitcher().process(confirm_callback=wrapped_confirm)

        if not switched:
            return 1

        self._wait_for_completion()
        return 0

    @staticmethod
    def _wait_for_completion():
        """阻塞等待 AppCompletionEvent，替代旧的轮询方式。"""
        completion_event = threading.Event()

        def on_completion(payload: AppCompletionEvent):
            completion_event.set()

        event_bus.subscribe(APP_COMPLETION, on_completion)
        try:
            completion_event.wait()
        finally:
            event_bus.unsubscribe(APP_COMPLETION, on_completion)


_cleanup_done = False


def log_and_exit(mark=False):
    """退出前的清理工作：恢复默认账户、记录运行时长。"""
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
    """监听 Ctrl+C，优雅退出。"""
    def handle_interrupt(signum, frame):
        log_and_exit(True)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_interrupt)


def handle_global_exception(exc_type, exc_value, exc_traceback):
    """兜底捕获未处理的异常，弹窗提示用户。"""
    if exc_type in (KeyboardInterrupt, SystemExit):
        sys.exit(0)
    if logger:
        logger.exception(
            "捕获到未处理异常, 请尝试重启程序或联系开发者.",
            exc_value,
            popup=True,
        )


def run_async_in_thread(loop, coro) -> None:
    """在独立线程中运行 asyncio 事件循环。"""
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
    """程序入口。"""
    global logger, CONFIG

    setup_dependency_injection()

    logger = create_logger_with_popup()
    CONFIG = ConfigService()

    with TASApp(VERSION) as app:
        return app.run()
