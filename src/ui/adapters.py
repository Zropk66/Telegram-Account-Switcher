"""UI适配器。"""
from typing import Callable

from src.ui.popup import Popup


def create_popup_handler() -> Callable[[str, str, str], None]:
    """创建弹窗处理器。"""

    def popup_handler(message: str, title: str, icon_type: str) -> None:
        """显示弹窗提示。"""
        with Popup.context():
            Popup.alert(message, title, icon_type)

    return popup_handler


__all__ = [
    'create_popup_handler',
]
