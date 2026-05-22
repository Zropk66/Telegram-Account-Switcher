"""全局消息弹窗管理器。"""

import sys
import threading
from typing import Literal, Optional

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox


class Popup(QObject):
    """全局弹窗管理器。"""

    _alert_signal = Signal(str, str, str)

    _instance: Optional["Popup"] = None
    _instance_lock = threading.Lock()
    _app: Optional[QApplication] = None
    _current_popup: Optional[QMessageBox] = None

    def __new__(cls, *args, **kwargs):
        """实现单例。"""
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
        self._alert_signal.connect(self._alert_on_main_thread)
        self._initialized = True

    @Slot(str, str, str)
    def _alert_on_main_thread(self, message: str, title: str, icon: str) -> None:
        """主线程展示弹窗。"""
        self._alert_impl(message, title, icon)

    @classmethod
    def reset_instance(cls) -> None:
        """重置弹窗单例状态。"""
        with cls._instance_lock:
            cls._instance = None
            cls._app = None
            cls._current_popup = None

    @classmethod
    def get_instance(cls) -> "Popup":
        """获取管理器单例。"""
        return cls()

    @classmethod
    def instance(cls) -> "Popup":
        """获取管理器单例。"""
        return cls()

    @classmethod
    def _ensure_app(cls) -> QApplication:
        """确保 QApplication 实例已初始化。"""
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
        """获取活跃的窗口。"""
        app = QApplication.instance()
        return app.activeWindow() if app else None

    @classmethod
    def _close_current(cls) -> None:
        """关闭活跃弹窗。"""
        if cls._current_popup is not None:
            cls._current_popup.close()
            cls._current_popup = None

    @classmethod
    def _alert_impl(
            cls,
            message: str,
            title: str = "提示",
            icon: str = "info"
    ) -> None:
        """显示提示框的具体实现。"""
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
    def alert(
            cls,
            message: str,
            title: str = "提示",
            icon: str = "info"
    ) -> None:
        """线程安全地弹出提示框。"""
        inst = cls.instance()
        if threading.current_thread() != threading.main_thread():
            inst._alert_signal.emit(message, title, icon)
        else:
            cls._alert_impl(message, title, icon)

    @classmethod
    def confirm(cls, message: str, title: str = "确认") -> bool:
        """弹出确认选择框。"""
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
        """提供消息泵上下文管理器。"""
        return _PopupContext()


class _PopupContext:
    """消息泵上下文。"""

    def __enter__(self):
        """进入上下文并确保应用程序实例化。"""
        Popup._ensure_app()
        return Popup

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文并处理挂起的事件。"""
        if Popup._app is not None:
            Popup._app.processEvents()
        return False


def alert(
        message: str,
        title: str = "提示",
        icon: Literal["info", "warning", "error", "question"] = "info"
) -> None:
    """弹出提示框。"""
    Popup.alert(message, title, icon)


def confirm(message: str, title: str = "确认") -> bool:
    """弹出确认选择框。"""
    return Popup.confirm(message, title)
