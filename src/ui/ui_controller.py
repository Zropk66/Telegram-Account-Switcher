"""
UI 控制器 -- 对外暴露弹窗相关的统一入口。

旧代码里弹窗有好几个名字（UIController / PopupManager / PopupSignalEmitter），
这里全部保留为别名，避免破坏已有引用。
"""
from typing import Literal

from src.ui.popup import Popup, alert, confirm

# -- 向后兼容的别名 --
UIController = Popup
PopupManager = Popup
PopupSignalEmitter = Popup


def emit_popup(
    message: str,
    title: str = "提示",
    icon: Literal["info", "warning", "error", "question"] = "info"
) -> None:
    """弹窗提示（旧接口，新代码请直接用 Popup.alert）。"""
    Popup.alert(message, title, icon)


def emit_confirm(message: str, title: str = "确认") -> bool:
    """确认弹窗（旧接口，新代码请直接用 Popup.confirm）。"""
    return Popup.confirm(message, title)


# 上下文管理器别名
PopupContext = Popup.context
PopupSession = Popup.context


def show_popup(message: str, title: str = "提示", icon: str = "info") -> None:
    """弹窗提示的另一个别名。"""
    Popup.alert(message, title, icon)


def ask_confirm(message: str, title: str = "确认") -> bool:
    """确认弹窗的另一个别名。"""
    return Popup.confirm(message, title)


__all__ = [
    "Popup",
    "UIController",
    "PopupManager",
    "PopupSignalEmitter",
    "PopupContext",
    "PopupSession",
    "alert",
    "confirm",
    "emit_popup",
    "emit_confirm",
    "show_popup",
    "ask_confirm",
]
