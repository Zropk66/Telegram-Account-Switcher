# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import json
import sys
import threading
from contextlib import suppress

from loguru import logger

from src.ui.ui_controller import alert


def setup_popup_handler():
    """配置弹窗处理器"""

    def popup_sink(message):
        extra = message.record.get("extra", {})
        if not extra.get("popup", False):
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

        alert(full_message, title=message.record["level"].name, icon=icon_type)

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

        with suppress(json.JSONDecodeError, IOError):
            from src.modules.config_manager import ConfigManage

            config_file = ConfigManage().config_file
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    if json.load(f).get("log_output", False):
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
