"""Telegram 账户切换器主入口."""

import os
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
    TASCLIException,
    recovery,
)
from src.core.cli_controller import CLIAction, CLIController
from src.core.process_manager import _hook_process_pool
from src.core.config import (
    ConfigData,
    ConfigService,
)
from src.core.config.key_manager import TelegramKeyManager
from src.core.constants import APP_TITLE, APP_VERSION, IPC_URL_PREFIX, LaunchMode
from src.core.logger import set_config_provider, set_popup_handler
from src.core.hook_ipc import HookIPCServer
from src.core.single_instance import SingleInstanceException, SingleInstanceLock
from src.core.utils import extract_tg_url
from src.ui.adapters import create_popup_handler
from src.ui.popup import Popup

logger: Logger
CONFIG: ConfigService
active_app: Optional["TASApp"] = None
_hook_ipc: Optional[HookIPCServer] = None
_url_bridge: Optional[object] = None

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


def _forward_url_with_fallback(pm, url: str, target_folder: str) -> None:
    """转发 URL，管道失败时回退到 hook 注入."""
    if not pm.forward_url_direct(url, target_folder):
        logger.info("直接管道连接失败，回退到 hook 注入方式")
        pm.forward_url(url, target_folder)


def _handle_tg_url(url: str) -> None:
    """处理 tg:// URL，转发到运行中的 Telegram 实例."""
    import time
    from src.core.process_manager import ProcessManager

    pm = ProcessManager(config=CONFIG, logger=logger)

    if CONFIG.launch_mode != LaunchMode.HOOK:
        pm.forward_url_symlink(url)
        return

    def _find_pipe_instances():
        return [(tag, folder, 0) for tag, folder in pm.find_running_instances_by_pipes()]

    instances = pm.get_running_instances() or _find_pipe_instances()

    if len(instances) == 0:
        logger.info("无运行中的实例，等待主进程启动账户...")
        for _ in range(10):
            time.sleep(1)
            instances = _find_pipe_instances()
            if instances:
                break

    if len(instances) == 0:
        logger.info("等待超时，自行启动默认账户并转发 URL")
        CONFIG.tag = CONFIG.default
        switcher = AccountSwitcher()
        if switcher.process() and switcher.monitor:
            if active_app and active_app.monitor:
                active_app.monitor.register_callback(
                    switcher.monitor.handle_process_status,
                    pid=_hook_process_pool.get(switcher.monitor.target_folder) if switcher.monitor.target_folder else None,
                )
            t = threading.Thread(
                target=switcher.monitor.run,
                daemon=True,
                name=f"Monitor-{switcher.monitor.tag}",
            )
            t.start()

            default_folder = CONFIG.get_account(CONFIG.default).get("folder") or "tdata"
            if pm.wait_for_instance(target_folder=default_folder, timeout=5):
                _forward_url_with_fallback(pm, url, default_folder)
            else:
                logger.error("实例启动超时，无法转发 URL")
        else:
            logger.error("默认账户启动失败，无法转发 URL")
    elif len(instances) == 1:
        logger.info(f"转发 URL 到唯一运行实例: {instances[0][0]}")
        _forward_url_with_fallback(pm, url, instances[0][1])
    else:
        logger.info(f"检测到 {len(instances)} 个运行实例，弹出选择框")
        if _url_bridge is None:
            logger.error("URL 选择桥接器未初始化")
            return

        selected = _url_bridge.select(instances, url)
        if selected:
            _forward_url_with_fallback(pm, url, selected)
        else:
            logger.info("用户取消了 URL 转发")


class TASApp:
    """账户切换应用程序."""

    def __init__(self, version: str) -> None:
        """初始化应用程序."""
        global active_app
        active_app = self
        self.version = version
        self.monitor = None
        Popup._ensure_app()
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
            Logger.set_debug(args.debug)
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:
            if logger:
                logger.error(f"参数解析失败: {e}")
            return 1

        config_file = Path(CONFIG.config_file)
        try:
            if not config_file.exists() or not self.cli_controller.check_config(args):
                from src.ui.settings_ui import open_settings_window

                open_settings_window(self.version)
                return 0
        except TASCLIException:
            return 1

        try:
            action = self.cli_controller.handle_actions(args)
        except TASCLIException:
            return 1

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
        else:
            CONFIG.config_check = True
        tags_str = CONFIG.tag or CONFIG.default
        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
        logger.info(f"切换账户: {tags_str}")

        def wrapped_confirm(msg: str) -> bool:
            """确认切换账户."""
            with Popup.context():
                return Popup.confirm(msg, "账户切换确认")

        monitors = []
        all_switched = True
        for current_tag in tags_list:
            CONFIG.tag = current_tag
            switcher = AccountSwitcher()
            switched = switcher.process(confirm_callback=wrapped_confirm)
            if not switched:
                logger.error(f"账户 '{current_tag}' 切换启动失败")
                all_switched = False
            elif switcher.monitor:
                monitors.append(switcher.monitor)

        if not all_switched and not monitors:
            return 1

        if monitors:
            import time
            logger.debug(f"启动 {len(monitors)} 个后台进程监控")
            self.monitor = ProcessMonitor(CONFIG.client, logger=logger)
            for account_monitor in monitors:
                self.monitor.register_callback(
                    account_monitor.handle_process_status,
                    pid=_hook_process_pool.get(account_monitor.target_folder) if account_monitor.target_folder else None,
                )
                t = threading.Thread(target=account_monitor.run, daemon=True, name=f"Monitor-{account_monitor.tag}")
                t.start()
            self.monitor.start_watching()
            try:
                while not all(m.completion_event.is_set() for m in monitors):
                    Popup.process_events()
                    time.sleep(0.1)
            except (KeyboardInterrupt, SystemExit):
                import traceback
                traceback.print_exc()
            finally:
                self.monitor.stop_watching()

        return 0


_cleanup_done = threading.Event()


def log_and_exit(mark: bool = False) -> None:
    """记录日志并退出."""
    global _cleanup_done, CONFIG, _hook_ipc
    if mark and _cleanup_done.is_set():
        return
    with suppress(Exception):
        if mark and CONFIG.config_check:
            _cleanup_done.set()
            recovery(config=CONFIG, logger=logger)

        if _hook_ipc:
            _hook_ipc.stop()
            _hook_ipc = None

        if CONFIG:
            CONFIG.shutdown()
            if CONFIG.log_output and CONFIG.start_time and logger:
                logger.info(f"运行时长：{CONFIG.watch_time()}")
    return


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

    if CONFIG and CONFIG.config_check:
        from contextlib import suppress as _suppress
        with _suppress(Exception):
            recovery(config=CONFIG, logger=logger)

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
    global logger, CONFIG, _hook_ipc, _url_bridge

    setup_dependency_injection()
    logger = create_logger_with_popup()
    CONFIG = ConfigService()

    from src.core.ipc import IPCClient, IPCServer

    tg_url = extract_tg_url(sys.argv[1:])

    if tg_url:
        if IPCClient.send_command(f"{IPC_URL_PREFIX}{tg_url}"):
            logger.info(f"已将 tg:// URL 转发至主 TAS 进程处理。")
            with suppress(Exception):
                CONFIG.shutdown()
            os._exit(0)
        sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if not a.lower().startswith("tg://")]

    cli_controller = CLIController(version=VERSION)
    try:
        parsed_args = cli_controller.parse_args()
        Logger.set_debug(parsed_args.debug)
        switch_target = parsed_args.switch if parsed_args.switch else CONFIG.default
    except Exception:
        switch_target = CONFIG.default

    if CONFIG.configs.get("single_instance", False):
        try:
            SingleInstanceLock.ensure_single_instance()
        except SingleInstanceException as e:
            if logger:
                logger.error(str(e), popup=True)
            return 1

    if not tg_url and IPCClient.send_command(switch_target):
        logger.info(f"已成功将切换目标 '{switch_target}' 发送至主 TAS 进程处理。")
        with suppress(Exception):
            CONFIG.shutdown()
        os._exit(0)

    Popup._ensure_app()
    from src.ui.url_selector import URLSelectorBridge
    _url_bridge = URLSelectorBridge()

    if CONFIG.launch_mode == LaunchMode.HOOK:
        def _handle_hook_exit(pid: int) -> None:
            if active_app and active_app.monitor:
                active_app.monitor.notify_exit(pid)

        def _resolve_tag(tdata_name: str) -> Optional[str]:
            for tag, info in CONFIG.tags.items():
                if info.get("folder") == tdata_name:
                    return tag
            default_folder = CONFIG.get_account(CONFIG.default).get("folder")
            if tdata_name == default_folder:
                return CONFIG.default
            return None

        _hook_ipc = HookIPCServer(
            logger=logger,
            url_handler=_handle_tg_url,
            exit_handler=_handle_hook_exit,
            tag_resolver=_resolve_tag,
        )
        _hook_ipc.start()

    def handle_remote_command(payload: str) -> None:
        def _execute() -> None:
            try:
                if payload.startswith(IPC_URL_PREFIX):
                    url = payload[len(IPC_URL_PREFIX):]
                    logger.info(f"收到远程 URL 指令: {url}")
                    _handle_tg_url(url)
                    return

                logger.info(f"收到远程多开指令目标: {payload}")
                validated_tags = cli_controller._validate_tag(payload)
                tags_list = [t.strip() for t in validated_tags.split(",") if t.strip()]
                for current_tag in tags_list:
                    CONFIG.tag = current_tag
                    switcher = AccountSwitcher()
                    if switcher.process() and switcher.monitor:
                        if active_app and active_app.monitor:
                            active_app.monitor.register_callback(
                                switcher.monitor.handle_process_status,
                                pid=_hook_process_pool.get(switcher.monitor.target_folder) if switcher.monitor.target_folder else None,
                            )
                        t = threading.Thread(
                            target=switcher.monitor.run,
                            daemon=True,
                            name=f"Monitor-{switcher.monitor.tag}",
                        )
                        t.start()
            except Exception as e:
                logger.error(f"处理远程指令发生错误: {e}")

        threading.Thread(target=_execute, daemon=True, name="IPC-Command-Handler").start()

    ipc_server = IPCServer(handle_remote_command, logger=logger)
    ipc_server.start()

    if tg_url:
        handle_remote_command(f"{IPC_URL_PREFIX}{tg_url}")

    logger.info("初始化成功")

    try:
        with TASApp(VERSION) as app:
            return app.run()
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        logger.exception("程序异常终止", e)
        return 1
    finally:
        ipc_server.stop()
