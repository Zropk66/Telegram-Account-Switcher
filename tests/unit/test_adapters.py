"""
UI 适配器单元测试。

验证 UI 层与核心业务层之间的桥接适配器，确保跨层通信的回调函数准确触发 UI 响应。
"""
import os
from unittest.mock import patch, MagicMock

# 设置 offscreen 模式，避免单元测试依赖真实显示器环境
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtWidgets import QApplication
from src.ui.adapters import create_cli_callbacks, create_info_handler, create_popup_handler
from src.ui.popup import Popup


@pytest.fixture(scope="module")
def qapp():
    """初始化 Qt 应用上下文，确保 UI 适配器能够正确实例化。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


class TestAdapters:
    """
    验证 UI 适配器模块的桥接与回调功能。
    """

    def test_create_cli_callbacks_returns_all_keys(self):
        """验证生成的 CLI 回调集合包含所有预期的处理接口。"""
        callbacks = create_cli_callbacks()

        expected_keys = {
            "help_handler",
            "settings_handler",
            "info_handler",
            "warning_handler",
            "error_handler"
        }

        assert set(callbacks.keys()) == expected_keys
        for key in expected_keys:
            assert callable(callbacks[key])

    def test_info_handler_calls_popup_alert_info(self, qapp):
        """验证信息提示处理器能正确调用弹窗模块展示提示信息。"""
        test_message = "测试信息"

        with patch.object(Popup, 'alert', return_value=None) as mock_alert:
            handler = create_info_handler()
            handler(test_message)

            mock_alert.assert_called_once_with(test_message, "提示", "info")

    def test_popup_handler_calls_popup_in_context(self, qapp):
        """验证弹窗处理器在正确的上下文环境下触发 UI 提示。"""
        test_message = "测试消息"
        test_title = "测试标题"
        test_icon = "info"

        context_used = False
        alert_called = False

        def mock_context():
            nonlocal context_used
            context_used = True
            class MockContext:
                def __enter__(self): pass
                def __exit__(self, *args): pass
            return MockContext()

        def mock_alert(message, title, icon):
            nonlocal alert_called
            alert_called = True
            assert message == test_message
            assert title == test_title
            assert icon == test_icon

        with patch.object(Popup, 'context', side_effect=mock_context), \
             patch.object(Popup, 'alert', side_effect=mock_alert):

            handler = create_popup_handler()
            handler(test_message, test_title, test_icon)

            assert context_used is True
            assert alert_called is True
