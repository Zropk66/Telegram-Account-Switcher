# -*- coding: utf-8 -*-
"""
UI适配器模块

将UI功能适配为core模块期望的回调接口。
这个模块是core和ui之间的桥梁，负责：
1. 将UI函数包装成core需要的回调格式
2. 处理参数转换
3. 提供统一的接口给main.py使用
"""

from typing import Callable

from src.ui.help_ui import open_help_window
from src.ui.settings_ui import open_settings_window
from src.ui.popup import Popup


# ============== CLIController 适配器 ==============

def create_help_handler() -> Callable[[str], None]:
    """创建帮助窗口处理器
    
    Returns:
        接收 version 参数的回调函数
    """
    def handler(version: str) -> None:
        open_help_window(version)
    return handler


def create_settings_handler() -> Callable[[str], None]:
    """创建设置窗口处理器
    
    Returns:
        接收 version 参数的回调函数
    """
    def handler(version: str) -> None:
        open_settings_window(version)
    return handler


def create_info_handler() -> Callable[[str], None]:
    """创建信息提示处理器
    
    Returns:
        接收 message 参数的回调函数
    """
    def handler(message: str) -> None:
        Popup.alert(message, "提示", "info")
    return handler


def create_warning_handler() -> Callable[[str], None]:
    """创建警告提示处理器
    
    Returns:
        接收 message 参数的回调函数
    """
    def handler(message: str) -> None:
        Popup.alert(message, "警告", "warning")
    return handler


def create_error_handler() -> Callable[[str], None]:
    """创建错误提示处理器
    
    Returns:
        接收 message 参数的回调函数
    """
    def handler(message: str) -> None:
        Popup.alert(message, "错误", "error")
    return handler


# ============== Logger 适配器 ==============

def create_popup_handler() -> Callable[[str, str, str], None]:
    """创建弹窗处理器
    
    Returns:
        接收 (message, title, icon) 参数的回调函数
    """
    def handler(message: str, title: str, icon: str) -> None:
        with Popup.context():
            Popup.alert(message, title, icon)
    return handler


# ============== 便捷函数：获取所有回调 ==============

def create_cli_callbacks() -> dict:
    """创建CLIController需要的所有回调
    
    Returns:
        包含所有回调函数的字典
    """
    return {
        "help_handler": create_help_handler(),
        "settings_handler": create_settings_handler(),
        "info_handler": create_info_handler(),
        "warning_handler": create_warning_handler(),
        "error_handler": create_error_handler(),
    }
