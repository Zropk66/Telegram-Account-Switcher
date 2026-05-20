"""
UI 适配器模块。

提供 UI 层与核心业务逻辑之间的适配器函数，将 UI 回调桥接到核心功能。
主要用于 CLI 控制器与 UI 组件之间的解耦。
"""

from typing import Dict, Callable

from src.ui.popup import Popup


def create_cli_callbacks() -> Dict[str, Callable]:
    """创建 CLI 控制器所需的 UI 回调集合。"""
    return {
        "help_handler": create_help_handler(),
        "settings_handler": create_settings_handler(),
        "info_handler": create_info_handler(),
        "warning_handler": create_warning_handler(),
        "error_handler": create_error_handler(),
    }


def create_help_handler() -> Callable[[str], None]:
    """创建帮助信息显示回调。"""

    def help_handler(version: str) -> None:
        """显示帮助窗口。"""
        from src.ui.help_ui import open_help_window
        open_help_window(version)

    return help_handler


def create_settings_handler() -> Callable[[str], None]:
    """创建设置窗口打开回调。"""

    def settings_handler(version: str) -> None:
        """打开设置窗口。"""
        from src.ui.settings_ui import open_settings_window
        open_settings_window(version)

    return settings_handler


def create_info_handler() -> Callable[[str], None]:
    """创建信息提示回调。"""

    def info_handler(message: str) -> None:
        """显示信息提示弹窗。"""
        Popup.alert(message, "提示", "info")

    return info_handler


def create_warning_handler() -> Callable[[str], None]:
    """创建警告提示回调。"""

    def warning_handler(message: str) -> None:
        """显示警告提示弹窗。"""
        Popup.alert(message, "警告", "warning")

    return warning_handler


def create_error_handler() -> Callable[[str], None]:
    """创建错误提示回调。"""

    def error_handler(message: str) -> None:
        """显示错误提示弹窗。"""
        Popup.alert(message, "错误", "error")

    return error_handler


def create_popup_handler() -> Callable[[str, str, str], None]:
    """创建弹窗处理器。"""

    def popup_handler(message: str, title: str, icon_type: str) -> None:
        """在 Popup 上下文中显示弹窗。"""
        with Popup.context():
            Popup.alert(message, title, icon_type)

    return popup_handler


__all__ = [
    'create_cli_callbacks',
    'create_help_handler',
    'create_settings_handler',
    'create_info_handler',
    'create_warning_handler',
    'create_error_handler',
    'create_popup_handler',
]
