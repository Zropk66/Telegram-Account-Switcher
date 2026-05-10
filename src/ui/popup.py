# -*- coding: utf-8 -*-
"""
全局弹窗管理器

提供全局唯一的弹窗功能，管理 QApplication 生命周期。
"""
import sys
from typing import Literal, Optional

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QMessageBox


class Popup(QObject):
    """
    全局弹窗管理器（单例）

    职责：
    - 管理全局唯一的 QApplication 实例
    - 直接显示弹窗（无需信号）
    - 确保全局只有一个弹窗实例

    使用方式:
        # 直接调用（推荐在已有 GUI 的程序中使用）
        Popup.alert("消息", "标题")
        result = Popup.confirm("确定吗？", "确认")

        # 使用上下文管理器（推荐在脚本中使用）
        with Popup.context():
            Popup.alert("消息")
    """

    _instance: Optional["Popup"] = None
    _app: Optional[QApplication] = None
    _current_popup: Optional[QMessageBox] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        super().__init__()
        self._initialized = True

    @classmethod
    def instance(cls) -> "Popup":
        """获取单例实例"""
        return cls()

    @classmethod
    def _ensure_app(cls) -> QApplication:
        """确保全局 QApplication 实例存在"""
        if cls._app is not None:
            return cls._app

        existing = QApplication.instance()
        if existing is not None:
            cls._app = existing
            return cls._app

        cls._app = QApplication(sys.argv)
        return cls._app

    @classmethod
    def _get_active_window(cls):
        """获取当前活动窗口"""
        app = QApplication.instance()
        return app.activeWindow() if app else None

    @classmethod
    def _close_current(cls) -> None:
        """关闭当前弹窗"""
        if cls._current_popup is not None:
            cls._current_popup.close()
            cls._current_popup = None

    @classmethod
    def alert(
        cls,
        message: str,
        title: str = "提示",
        icon: Literal["info", "warning", "error", "question"] = "info"
    ) -> None:
        """
        显示提示弹窗

        Args:
            message: 消息内容
            title: 弹窗标题
            icon: 图标类型
        """
        cls._ensure_app()
        cls._close_current()

        icon_map = {
            "info": QMessageBox.Icon.Information,
            "warning": QMessageBox.Icon.Warning,
            "error": QMessageBox.Icon.Critical,
            "question": QMessageBox.Icon.Question,
        }

        msg_box = QMessageBox(cls._get_active_window())
        msg_box.setWindowTitle(str(title).upper())
        msg_box.setText(str(message))
        msg_box.setIcon(icon_map.get(icon, QMessageBox.Icon.Information))

        cls._current_popup = msg_box
        msg_box.finished.connect(lambda: cls._close_current())
        msg_box.exec()

    @classmethod
    def confirm(cls, message: str, title: str = "确认") -> bool:
        """
        显示确认弹窗

        Args:
            message: 确认消息
            title: 弹窗标题

        Returns:
            用户是否点击了"是"
        """
        cls._ensure_app()
        cls._close_current()

        msg_box = QMessageBox(cls._get_active_window())
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.Yes)

        cls._current_popup = msg_box
        result = msg_box.exec()
        cls._current_popup = None

        return result == QMessageBox.Yes

    @classmethod
    def context(cls):
        """
        获取上下文管理器

        使用方式:
            with Popup.context():
                Popup.alert("消息")
        """
        return _PopupContext()


class _PopupContext:
    """弹窗上下文管理器（内部类）"""

    def __enter__(self):
        Popup._ensure_app()
        return Popup

    def __exit__(self, exc_type, exc_val, exc_tb):
        if Popup._app is not None:
            Popup._app.processEvents()
        return False


# 便捷函数
def alert(
    message: str,
    title: str = "提示",
    icon: Literal["info", "warning", "error", "question"] = "info"
) -> None:
    """弹窗提示"""
    Popup.alert(message, title, icon)


def confirm(message: str, title: str = "确认") -> bool:
    """确认弹窗"""
    return Popup.confirm(message, title)
