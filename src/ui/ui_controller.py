# -*- coding: utf-8 -*-
from typing import Literal

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMessageBox


class UIController(QObject):
    """全局 UI 信号和弹窗控制器"""

    _instance = None

    # 信号定义
    show_popup_signal = Signal(str, str, str)  # title, message, icon_type
    confirm_request_signal = Signal(str, str, object)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        super().__init__()
        self._initialized = True

        # 连接信号到槽
        self.show_popup_signal.connect(self._handle_show_popup)
        self.confirm_request_signal.connect(self._handle_confirm_request)

    @staticmethod
    def instance():
        return UIController()

    def _get_active_window(self):
        """获取当前活动窗口作为父窗口"""
        app = QApplication.instance()
        if app:
            return app.activeWindow()
        return None

    def _handle_show_popup(self, title: str, message: str, icon_type: str):
        """实际显示弹窗的槽函数"""
        if QApplication.instance() is None:
            return

        icon_map = {
            "info": QMessageBox.Icon.Information,
            "warning": QMessageBox.Icon.Warning,
            "error": QMessageBox.Icon.Critical,
            "question": QMessageBox.Icon.Question,
        }

        msg_box = QMessageBox(self._get_active_window())
        msg_box.setWindowTitle(str(title).upper())
        msg_box.setText(str(message))
        msg_box.setIcon(icon_map.get(icon_type, QMessageBox.Icon.Information))
        msg_box.exec()

    def _handle_confirm_request(self, message: str, title: str, result_holder: dict):
        """实际显示确认框的槽函数"""
        if QApplication.instance() is None:
            result_holder["res"] = False
            return

        reply = QMessageBox.question(
            self._get_active_window(),
            title,
            message,
            QMessageBox.Yes | QMessageBox.No
        )
        result_holder["res"] = (reply == QMessageBox.Yes)


def alert(
    message: str,
    title: str = "提示",
    icon: Literal["info", "warning", "error", "question"] = "info",
):
    """弹窗提示"""
    UIController.instance().show_popup_signal.emit(title, message, icon)


def confirm(message: str, title: str = "确认") -> bool:
    """确认弹窗"""
    result_holder = {"res": False}
    UIController.instance().confirm_request_signal.emit(message, title, result_holder)
    return result_holder["res"]
