# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import json
import logging
import os
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox


def show_message(title, message, level):
    """显示弹窗"""
    app = QApplication.instance() or QApplication(sys.argv)
    msgBox = QMessageBox()
    msgBox.setWindowTitle(logging.getLevelName(title).upper())
    msgBox.setText(message)
    msgBox.setIcon(level)
    msgBox.exec()


def format_exception(exception):
    """格式化异常为字符串"""
    return "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))


class popup_filter(logging.Filter):
    """过滤器"""

    def filter(self, record):
        if record.levelno in {logging.TIPS, logging.CRITICAL}:
            try:
                if isinstance(record.msg, BaseException):
                    message = format_exception(record.msg)
                else:
                    message = record.msg

                supportLevels = {
                    logging.TIPS: QMessageBox.Warning,
                    logging.CRITICAL: QMessageBox.Critical,
                }
                if not (record.levelno in supportLevels.keys()):
                    return True
                for k, v in supportLevels.items():
                    if record.levelno == k:
                        show_message(k, message, v)
                    if record.levelno == logging.CRITICAL:
                        return True
                    return False
            except (AttributeError, TypeError, Exception):
                return False
        return record.levelno not in {logging.TIPS, logging.CRITICAL}


class TAS_logger:
    """初始化"""
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._init_logger()
        return cls._instance

    def _init_logger(self):
        self.logger = logging.getLogger('TAS_logger')
        self.logger.setLevel(logging.DEBUG)

        TIPS_LEVEL_NUM = 25
        logging.addLevelName(TIPS_LEVEL_NUM, "TIPS")
        setattr(logging, 'TIPS', TIPS_LEVEL_NUM)
        setattr(logging.Logger, 'tips',
                lambda self, msg, *args, **kwargs:
                self._log(TIPS_LEVEL_NUM, msg, args, **kwargs))

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        console_handler = logging.StreamHandler()
        file_handler = logging.FileHandler("TAS_log.txt", mode='a', encoding='utf-8')

        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        self.logger.addFilter(popup_filter())
        self.logger.addHandler(console_handler)
        try:
            with open(Path(os.path.join(os.getcwd(), 'configs.json')), 'r', encoding='utf-8') as f:
                if json.load(f).get('log_output'):
                    self.logger.addHandler(file_handler)
        except (FileNotFoundError, json.JSONDecodeError, IOError):
            pass
        self.logger.propagate = False


logger = TAS_logger().logger
