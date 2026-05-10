import sys
import threading
from contextlib import suppress
from typing import Callable, Optional, Protocol

from loguru import logger

# 弹窗处理器：接收 (message, title, icon_type)
PopupHandler = Callable[[str, str, str], None]

# 用字典包装，确保闭包总能拿到最新的 handler
_popup_state: dict = {"handler": None}


class ConfigProvider(Protocol):
    """配置提供者接口，用于依赖注入。"""

    def get(self, key: str, default: any = None) -> any:
        """读取配置项。"""
        ...


class DefaultConfigProvider:
    """没有外部提供者时的兜底实现，始终返回默认值。"""

    def get(self, key: str, default: any = None) -> any:
        return default


# 全局配置提供者，默认使用兜底实现
_config_provider: ConfigProvider = DefaultConfigProvider()


def set_config_provider(provider: ConfigProvider) -> None:
    """替换全局配置提供者，需实现 ``get(key, default)`` 方法。"""
    global _config_provider
    _config_provider = provider


def set_popup_handler(handler: Optional[PopupHandler]) -> None:
    """设置弹窗处理器，签名为 ``(message, title, icon_type) -> None``，传入 ``None`` 可移除。"""
    _popup_state["handler"] = handler


def setup_popup_handler():
    """把 loguru 的 popup 级别日志桥接到注入的弹窗处理器。"""

    def popup_sink(message):
        extra = message.record.get("extra", {})
        if not extra.get("popup", False):
            return

        handler = _popup_state.get("handler")
        if handler is None:
            return

        level_map = {
            "DEBUG": "info",
            "INFO": "info",
            "WARNING": "warning",
            "ERROR": "error",
            "CRITICAL": "error",
            "EXCEPTION": "error",
        }

        icon_type = level_map.get(message.record["level"].name, "info")
        full_message = message.record["message"]

        if exception := message.record.get("exception", None):
            full_message += f"\n\n{exception}"

        handler(full_message, message.record["level"].name, icon_type)

    logger.add(popup_sink, filter=lambda record: record["extra"].get("popup", False))


class Logger:
    """基于 loguru 的单例日志器，支持文件输出和弹窗通知。"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_logger()
        return cls._instance

    @staticmethod
    def _init_logger():
        """配置 loguru：移除默认 sink，添加控制台和可选的文件输出。"""
        logger.remove()

        logger.level("EXCEPTION", no=45, color="<red>", icon="❌")

        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        )
        with suppress(TypeError):
            logger.add(sys.stderr, format=log_format, level="DEBUG", colorize=True)

        if _config_provider.get("log_output", False):
            logger.add(
                "TAS.log",
                rotation="10 MB",
                encoding="utf-8",
                format=log_format,
                level="DEBUG",
            )

        setup_popup_handler()

    @staticmethod
    def log(level, message, popup=False, **kwargs):
        """写入一条日志，``popup=True`` 时同时弹窗。"""
        exc = kwargs.pop("exc", None)
        logger.opt(exception=exc, depth=1).bind(popup=popup, **kwargs).log(
            level, message
        )

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
