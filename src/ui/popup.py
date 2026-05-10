"""
全局弹窗管理器。

整个应用共用一个 QApplication 实例，弹窗通过 Popup 类按需弹出，
也可以用 `with Popup.context():` 在脚本场景下临时创建事件循环。
"""
import sys
from typing import Literal, Optional

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QMessageBox


class Popup(QObject):
    """
    单例弹窗管理器。

    直接调用类方法即可弹窗，不需要手动创建实例：

        Popup.alert("消息", "标题")
        ok = Popup.confirm("确定吗？")

    在没有 GUI 事件循环的场景下，用上下文管理器包一下：

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
        return cls()

    @classmethod
    def _ensure_app(cls) -> QApplication:
        """确保全局 QApplication 存在，没有就创建一个。"""
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
        app = QApplication.instance()
        return app.activeWindow() if app else None

    @classmethod
    def _close_current(cls) -> None:
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
        """弹出指定标题和图标类型的提示消息框。"""
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
        """弹出 Yes/No 确认框，返回用户是否点击了"是"。"""
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
        """返回一个上下文管理器，在进入时确保 QApplication 就绪。"""
        return _PopupContext()


class _PopupContext:
    """内部上下文管理器，退出时刷一次事件循环。"""

    def __enter__(self):
        Popup._ensure_app()
        return Popup

    def __exit__(self, exc_type, exc_val, exc_tb):
        if Popup._app is not None:
            Popup._app.processEvents()
        return False


# -- 模块级便捷函数 --

def alert(
    message: str,
    title: str = "提示",
    icon: Literal["info", "warning", "error", "question"] = "info"
) -> None:
    """弹窗提示的快捷入口。"""
    Popup.alert(message, title, icon)


def confirm(message: str, title: str = "确认") -> bool:
    """确认弹窗的快捷入口。"""
    return Popup.confirm(message, title)
