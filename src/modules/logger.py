# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import threading
import json
import sys

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QObject, Signal
from contextlib import suppress
from loguru import logger


class LogSignals(QObject):
    show_popup = Signal(str, str, QMessageBox.Icon)


log_signals = LogSignals()


def show_message(title, message, level):
    """显示弹窗"""
    app = QApplication.instance() or QApplication(sys.argv)
    msg_box = QMessageBox()
    msg_box.setWindowTitle(title.upper())
    msg_box.setText(message)
    msg_box.setIcon(level)
    msg_box.exec()


def setup_popup_handler():
    """弹窗处理器"""

    def popup_sink(message):
        extra = message.record.get('extra', {})
        if not extra.get('popup', False):
            return

        level_map = {
            'DEBUG': QMessageBox.Information,
            'INFO': QMessageBox.Information,
            'WARNING': QMessageBox.Warning,
            'ERROR': QMessageBox.Critical,
            'CRITICAL': QMessageBox.Critical,
            'EXCEPTION': QMessageBox.Critical,
        }

        level_icon = level_map.get(message.record['level'].name, QMessageBox.Information)
        full_message = message.record['message']

        if exception := message.record.get('exception', None):
            full_message += f"\n\n{exception}"

        log_signals.show_popup.emit(message.record['level'].name, full_message, level_icon)

    logger.add(popup_sink, filter=lambda record: record['extra'].get('popup', False))


log_signals.show_popup.connect(show_message)


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

        logger.add(
            sys.stderr,
            format=log_format,
            level="DEBUG",
            colorize=True
        )

        with suppress(json.JSONDecodeError, IOError):
            from src.modules.config_manager import ConfigManage
            config_file = ConfigManage().config_file
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    if json.load(f).get('log_output', False):
                        logger.add(
                            "TAS.log",
                            rotation="10 MB",
                            encoding="utf-8",
                            format=log_format,
                            level="DEBUG"
                        )

        setup_popup_handler()

    @staticmethod
    def log(level, message, popup=False, **kwargs):
        """通用日志记录方法"""

        exc = kwargs.pop('exc', None)
        logger.opt(exception=exc, depth=1).bind(popup=popup, **kwargs).log(level, message)

    def debug(self, message, popup=False, **kwargs):
        self.log('DEBUG', message, popup, **kwargs)

    def info(self, message, popup=False, **kwargs):
        self.log('INFO', message, popup, **kwargs)

    def warning(self, message, popup=False, **kwargs):
        self.log('WARNING', message, popup, **kwargs)

    def error(self, message, popup=False, **kwargs):
        self.log('ERROR', message, popup, **kwargs)

    def critical(self, message, popup=False, **kwargs):
        self.log('CRITICAL', message, popup, **kwargs)

    def exception(self, message, exc, popup=False, **kwargs):
        kwargs["exc"] = exc
        self.log('EXCEPTION', message, popup, **kwargs)
