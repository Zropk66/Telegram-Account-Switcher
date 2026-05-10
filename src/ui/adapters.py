"""
UI 适配器 -- 把 UI 层的弹窗/窗口封装成 core 模块需要的回调签名。

core 模块不直接依赖 PySide6，所以需要在这里做一层薄薄的适配。
"""

from typing import Callable

from src.ui.help_ui import open_help_window
from src.ui.popup import Popup
from src.ui.settings_ui import open_settings_window


# -- CLIController 回调 --

def create_help_handler() -> Callable[[str], None]:
    """返回一个打开帮助窗口的回调，供 CLIController 调用。"""

    def handler(version: str) -> None:
        open_help_window(version)
    return handler


def create_settings_handler() -> Callable[[str], None]:
    """返回一个打开设置窗口的回调，供 CLIController 调用。"""

    def handler(version: str) -> None:
        open_settings_window(version)
    return handler


def create_info_handler() -> Callable[[str], None]:
    """返回一个 info 级别弹窗回调。"""

    def handler(message: str) -> None:
        Popup.alert(message, "提示", "info")
    return handler


def create_warning_handler() -> Callable[[str], None]:
    """返回一个 warning 级别弹窗回调。"""

    def handler(message: str) -> None:
        Popup.alert(message, "警告", "warning")
    return handler


def create_error_handler() -> Callable[[str], None]:
    """返回一个 error 级别弹窗回调。"""

    def handler(message: str) -> None:
        Popup.alert(message, "错误", "error")
    return handler


# -- Logger 回调 --

def create_popup_handler() -> Callable[[str, str, str], None]:
    """返回一个通用弹窗回调，Logger 通过它来弹消息。"""

    def handler(message: str, title: str, icon: str) -> None:
        with Popup.context():
            Popup.alert(message, title, icon)
    return handler


# -- 批量获取 --

def create_cli_callbacks() -> dict:
    """一次性拿到 CLIController 需要的全部回调。"""
    return {
        "help_handler": create_help_handler(),
        "settings_handler": create_settings_handler(),
        "info_handler": create_info_handler(),
        "warning_handler": create_warning_handler(),
        "error_handler": create_error_handler(),
    }
