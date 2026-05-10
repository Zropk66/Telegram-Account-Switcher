# -*- coding: utf-8 -*-
"""
UI 控制器

提供全局 UI 相关的便捷接口。
"""
from typing import Literal

from src.ui.popup import Popup, alert, confirm


# 保持向后兼容的别名
UIController = Popup
PopupManager = Popup
PopupSignalEmitter = Popup


def emit_popup(
    message: str,
    title: str = "提示",
    icon: Literal["info", "warning", "error", "question"] = "info"
) -> None:
    """发出弹窗（向后兼容）"""
    Popup.alert(message, title, icon)


def emit_confirm(message: str, title: str = "确认") -> bool:
    """发出确认（向后兼容）"""
    return Popup.confirm(message, title)


# 上下文管理器
PopupContext = Popup.context
PopupSession = Popup.context


def show_popup(message: str, title: str = "提示", icon: str = "info") -> None:
    """显示弹窗"""
    Popup.alert(message, title, icon)


def ask_confirm(message: str, title: str = "确认") -> bool:
    """询问确认"""
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
