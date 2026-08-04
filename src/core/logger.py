"""日志模块."""

import sys
import threading
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Callable, Optional, Protocol

from loguru import logger as loguru_logger

if TYPE_CHECKING:
    from loguru import Message

PopupHandler = Callable[[str, str, str], None]

_popup_state: dict[str, Optional[PopupHandler]] = {"handler": None}
_exception_level_registered = False


class ConfigProvider(Protocol):
    """配置读取接口."""

    def get(self, key: str, default: Any = None) -> Any:  # noqa: ANN401
        """获取配置项的值."""
        ...


class DefaultConfigProvider(ConfigProvider):
    """默认配置实现."""

    def get(self, key: str, default: Any = None) -> Any:  # noqa: ANN401
        """获取配置值."""
        return default


_config_provider: ConfigProvider = DefaultConfigProvider()


def set_config_provider(provider: ConfigProvider) -> None:
    """注入配置提供者."""
    global _config_provider
    _config_provider = provider


def set_popup_handler(handler: Optional[PopupHandler]) -> None:
    """设置弹窗处理器."""
    _popup_state["handler"] = handler


def reset_logger_state() -> None:
    """重置全局日志状态."""
    global _config_provider
    Logger.reset_instance()
    _popup_state["handler"] = None
    _config_provider = DefaultConfigProvider()


def _setup_popup_bridge() -> None:
    """桥接日志流到UI弹窗."""

    def popup_sink(message: "Message") -> None:
        """发送日志弹窗."""
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

        if callable(handler):
            handler(full_message, level_name, icon_type)

    loguru_logger.add(popup_sink, filter=lambda r: r["extra"].get("popup", False))


class Logger:
    """日志管理器."""

    _instance = None
    _lock = threading.Lock()
    _debug_mode = False

    def __new__(cls, *args: Any, **kwargs: Any) -> "Logger":  # noqa: ANN401
        """实现日志单例."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_logger()
        return cls._instance

    @classmethod
    def set_debug(cls, debug: bool) -> None:
        """设置调试模式并重新初始化日志."""
        cls._debug_mode = debug
        cls._init_logger()

    @classmethod
    def get_instance(cls) -> "Logger":
        """获取日志单例."""
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """释放日志单例."""
        loguru_logger.remove()
        cls._instance = None
        cls._debug_mode = False

    @classmethod
    def _init_logger(cls) -> None:
        """初始化日志配置."""
        global _exception_level_registered
        loguru_logger.remove()

        if not _exception_level_registered:
            with suppress(ValueError):
                loguru_logger.level("EXCEPTION", no=45, color="<red>", icon="❌")
                _exception_level_registered = True

        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>"
        )

        min_level = "DEBUG" if cls._debug_mode else "INFO"

        if sys.stderr is not None:
            loguru_logger.add(sys.stderr, format=log_format, level=min_level, colorize=True)
        if _config_provider.get("log_output", False):
            loguru_logger.add(
                "TAS.log",
                rotation="10 MB",
                encoding="utf-8",
                format=log_format,
                level=min_level,
            )

        _setup_popup_bridge()

    @staticmethod
    def log(level: str, message: str, popup: bool = False, **kwargs: Any) -> None:  # noqa: ANN401
        """记录日志."""
        exc = kwargs.pop("exc", None)
        loguru_logger.opt(exception=exc, depth=2).bind(popup=popup, **kwargs).log(level, message)

    def debug(self, message: str, popup: bool = False, **kwargs: Any) -> None:  # noqa: ANN401
        """记录调试日志."""
        self.log("DEBUG", message, popup, **kwargs)

    def info(self, message: str, popup: bool = False, **kwargs: Any) -> None:  # noqa: ANN401
        """记录普通日志."""
        self.log("INFO", message, popup, **kwargs)

    def warning(self, message: str, popup: bool = False, **kwargs: Any) -> None:  # noqa: ANN401
        """记录警告日志."""
        self.log("WARNING", message, popup, **kwargs)

    def error(self, message: str, popup: bool = False, **kwargs: Any) -> None:  # noqa: ANN401
        """记录错误日志."""
        self.log("ERROR", message, popup, **kwargs)

    def critical(self, message: str, popup: bool = False, **kwargs: Any) -> None:  # noqa: ANN401
        """记录严重错误日志."""
        self.log("CRITICAL", message, popup, **kwargs)

    def exception(
        self,
        message: str,
        exc: Optional[BaseException],
        popup: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """记录异常日志."""
        kwargs["exc"] = exc
        self.log("EXCEPTION", message, popup, **kwargs)
