"""
日志模块。

基于 loguru 封装。
"""
import sys
import threading
from contextlib import suppress
from typing import Any, Callable, Optional, Protocol

from loguru import logger as loguru_logger
from src.core.interfaces import ILogger

PopupHandler = Callable[[str, str, str], None]

_popup_state: dict = {"handler": None}
_exception_level_registered = False


class ConfigProvider(Protocol):
    """配置读取契约，用于日志模块在初始化时判断是否需要输出到文件。"""

    def get(self, key: str, default: Any = None) -> Any: ...


class DefaultConfigProvider(ConfigProvider):
    """默认兜底配置，不输出文件。"""

    def get(self, key: str, default: Any = None) -> Any:
        return default


_config_provider: ConfigProvider = DefaultConfigProvider()


def set_config_provider(provider: ConfigProvider) -> None:
    """注入真实的配置提供者。"""
    global _config_provider
    _config_provider = provider


def set_popup_handler(handler: Optional[PopupHandler]) -> None:
    """注入 UI 层的弹窗逻辑。"""
    _popup_state["handler"] = handler


def reset_logger_state() -> None:
    """恢复日志模块的全局注入状态，供测试隔离使用。"""
    global _config_provider
    Logger.reset_instance()
    _popup_state["handler"] = None
    _config_provider = DefaultConfigProvider()


def _setup_popup_bridge():
    """将 loguru 的日志流通过 Sink 桥接到 UI 弹窗。"""

    def popup_sink(message):
        extra = message.record.get("extra", {})
        if not extra.get("popup", False):
            return

        handler = _popup_state.get("handler")
        if not handler:
            return

        level_name = message.record["level"].name
        level_map = {
            "DEBUG": "info",
            "INFO": "info",
            "WARNING": "warning",
            "ERROR": "error",
            "CRITICAL": "error",
            "EXCEPTION": "error",
        }

        icon_type = level_map.get(level_name, "info")
        full_message = message.record["message"]

        if exception := message.record.get("exception", None):
            full_message += f"\n\n{exception}"

        handler(full_message, level_name, icon_type)

    loguru_logger.add(popup_sink, filter=lambda r: r["extra"].get("popup", False))


class Logger(ILogger):
    """日志管理器。"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_logger()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "Logger":
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """释放当前日志单例和 loguru sink，供测试隔离使用。"""
        loguru_logger.remove()
        cls._instance = None

    @staticmethod
    def _init_logger():
        global _exception_level_registered
        loguru_logger.remove()

        if not _exception_level_registered:
            with suppress(ValueError):
                loguru_logger.level("EXCEPTION", no=45, color="<red>", icon="❌")
                _exception_level_registered = True

        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        )

        loguru_logger.add(sys.stderr, format=log_format, level="DEBUG", colorize=True)

        if _config_provider.get("log_output", False):
            loguru_logger.add(
                "TAS.log",
                rotation="10 MB",
                encoding="utf-8",
                format=log_format,
                level="DEBUG",
            )

        _setup_popup_bridge()

    @staticmethod
    def log(level: str, message: str, popup: bool = False, **kwargs) -> None:
        exc = kwargs.pop("exc", None)
        loguru_logger.opt(exception=exc, depth=2).bind(popup=popup, **kwargs).log(level, message)

    def debug(self, message, popup=False, **kwargs):
        self.log("DEBUG", message, popup, **kwargs)

    def info(self, message, popup=False, **kwargs):
        self.log("INFO", message, popup, **kwargs)

    def warning(self, message, popup=False, **kwargs):
        self.log("WARNING", message, popup, **kwargs)

    def error(self, message, popup=False, **kwargs):
        self.log("ERROR", message, popup, **kwargs)

    def critical(self, message, popup=False, **kwargs):
        self.log("CRITICAL", message, popup, **kwargs)

    def exception(self, message, exc, popup=False, **kwargs):
        kwargs["exc"] = exc
        self.log("EXCEPTION", message, popup, **kwargs)
