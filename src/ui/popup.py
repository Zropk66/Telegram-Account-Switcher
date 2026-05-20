"""
全局弹窗管理器，提供统一且线程安全的弹窗交互接口。

基于 PySide6 实现，确保应用在 GUI 模式或脚本上下文（通过上下文管理器）
下均能稳定弹出提示框与确认框。
"""

import sys
import threading
from typing import Literal, Optional

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QMessageBox


class Popup(QObject):
    """
    单例弹窗管理器，负责封装 QMessageBox 操作。

    可直接调用类方法 (`Popup.alert`, `Popup.confirm`) 进行操作，
    在脚本环境下，建议通过 `with Popup.context()` 管理事件循环。
    """

    _instance: Optional["Popup"] = None
    _instance_lock = threading.Lock()
    _app: Optional[QApplication] = None
    _current_popup: Optional[QMessageBox] = None

    def __new__(cls, *args, **kwargs):
        """内部方法：__new__。"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化。"""
        if hasattr(self, "_initialized"):
            return
        super().__init__()
        self._initialized = True

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例状态，主要用于测试清理。"""
        with cls._instance_lock:
            cls._instance = None
            cls._app = None
            cls._current_popup = None

    @classmethod
    def get_instance(cls) -> "Popup":
        """获取 Popup 实例。"""
        return cls()

    @classmethod
    def instance(cls) -> "Popup":
        """获取 Popup 实例的快捷方式。"""
        return cls()

    @classmethod
    def _ensure_app(cls) -> QApplication:
        """确保 QApplication 实例就绪，它是弹窗显示的前置条件。"""
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
        """获取当前活动的 UI 窗口。"""
        app = QApplication.instance()
        return app.activeWindow() if app else None

    @classmethod
    def _close_current(cls) -> None:
        """关闭当前挂起的弹窗。"""
        if cls._current_popup is not None:
            cls._current_popup.close()
            cls._current_popup = None

    @classmethod
    def alert(
            cls,
            message: str,
            title: str = "提示",
            icon: str = "info"
    ) -> None:
        """弹出提示框，阻塞直到用户确认。"""
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
        """弹出确认对话框，返回用户是否点击“是”。"""
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
        """返回弹窗上下文管理器，支持在非 GUI 循环场景下操作。"""
        return _PopupContext()


class _PopupContext:
    """提供进入/退出上下文时的自动状态管理。"""

    def __enter__(self):
        """内部方法：__enter__。"""
        Popup._ensure_app()
        return Popup

    def __exit__(self, exc_type, exc_val, exc_tb):
        """内部方法：__exit__。"""
        if Popup._app is not None:
            Popup._app.processEvents()
        return False


def alert(
        message: str,
        title: str = "提示",
        icon: Literal["info", "warning", "error", "question"] = "info"
) -> None:
    """提示框全局快捷函数。"""
    Popup.alert(message, title, icon)


def confirm(message: str, title: str = "确认") -> bool:
    """确认框全局快捷函数。"""
    return Popup.confirm(message, title)
