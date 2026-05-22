"""UI适配器单元测试。"""
import os
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from src.ui.adapters import create_popup_handler
from src.ui.popup import Popup

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="module")
def qapp():
    """初始化 Qt 应用上下文，确保 UI 适配器能够正确实例化。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


class TestAdapters:
    """验证 UI 适配器的桥接与回调功能。"""

    def test_popup_handler_calls_popup_in_context(self, qapp):
        """验证弹窗处理器在正确的上下文环境下触发 UI 提示。"""
        test_message = "测试消息"
        test_title = "测试标题"
        test_icon = "info"

        context_used = False
        alert_called = False

        def mock_context():
            """模拟上下文环境。"""
            nonlocal context_used
            context_used = True
            class MockContext:
                """模拟上下文。"""
                def __enter__(self): pass
                def __exit__(self, *args): pass
            return MockContext()

        def mock_alert(message, title, icon):
            """模拟弹窗提示。"""
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
