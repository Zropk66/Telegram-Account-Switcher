# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import sys
import threading
from contextlib import suppress
from typing import Callable, Optional, Protocol

from loguru import logger


# 弹窗处理器类型：接收 (message, title, icon_type) 参数
PopupHandler = Callable[[str, str, str], None]

# 使用字典存储处理器，确保闭包能正确引用（避免全局变量捕获问题）
_popup_state: dict = {"handler": None}


class ConfigProvider(Protocol):
    """配置提供者协议 - 用于依赖注入"""

    def get(self, key: str, default: any = None) -> any:
        """获取配置项"""
        ...


class DefaultConfigProvider:
    """默认配置提供者 - 当没有外部提供者时使用"""

    def get(self, key: str, default: any = None) -> any:
        return default


# 全局配置提供者，可通过依赖注入替换
_config_provider: ConfigProvider = DefaultConfigProvider()


def set_config_provider(provider: ConfigProvider) -> None:
    """
    设置配置提供者（依赖注入入口）

    Args:
        provider: 配置提供者，需实现 get(key, default) 方法

    Example:
        def my_provider(key, default=None):
            return my_config.get(key, default)

        set_config_provider(my_provider)
    """
    global _config_provider
    _config_provider = provider


def set_popup_handler(handler: Optional[PopupHandler]) -> None:
    """
    设置弹窗处理器（依赖注入入口）

    Args:
        handler: 弹窗处理函数，签名 (message: str, title: str, icon_type: str) -> None
                 传入 None 可移除当前处理器

    Example:
        def my_popup(message, title, icon_type):
            # 自定义弹窗逻辑
            pass

        set_popup_handler(my_popup)
    """
    _popup_state["handler"] = handler


def setup_popup_handler():
    """配置弹窗处理器（使用注入的处理器）"""

    def popup_sink(message):
        extra = message.record.get("extra", {})
        if not extra.get("popup", False):
            return

        # 从字典获取处理器，确保获取最新值
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

        # 调用注入的处理器
        handler(full_message, message.record["level"].name, icon_type)

    logger.add(popup_sink, filter=lambda record: record["extra"].get("popup", False))


class Logger:
    """日志记录器"""

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
        """初始化"""
        logger.remove()

        logger.level("EXCEPTION", no=45, color="<red>", icon="❌")

        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        )
        with suppress(TypeError):
            logger.add(sys.stderr, format=log_format, level="DEBUG", colorize=True)

        # 使用注入的配置提供者读取配置
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
        """记录日志"""

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
