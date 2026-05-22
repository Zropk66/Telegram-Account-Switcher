"""弹窗管理器单元测试。"""
import os
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QMessageBox, QApplication
from src.ui.popup import Popup


class TestPopup:
    """覆盖弹窗管理器的基础交互与生命周期约束。"""

    def test_singleton_returns_same_instance(self):
        """验证弹窗管理器始终复用同一个实例。"""
        Popup.reset_instance()

        instance1 = Popup()
        instance2 = Popup()

        assert instance1 is instance2

    def test_alert_sets_correct_icon(self, qapp):
        """验证错误弹窗使用 Critical 图标，避免严重问题被弱化展示。"""
        captured_icon = None

        def mock_setIcon(icon):
            """模拟设置图标。"""
            nonlocal captured_icon
            captured_icon = icon

        with patch.object(QMessageBox, 'exec', return_value=None), \
             patch.object(QMessageBox, 'setIcon', side_effect=mock_setIcon):
            Popup.alert("测试消息", "测试标题", "error")

            assert captured_icon == QMessageBox.Icon.Critical

    def test_confirm_returns_true_on_yes(self, qapp):
        """验证用户确认时返回 True。"""
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Yes):
            result = Popup.confirm("确定吗？", "确认")

            assert result is True

    def test_confirm_returns_false_on_no(self, qapp):
        """验证用户取消时返回 False。"""
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.No):
            result = Popup.confirm("确定吗？", "确认")

            assert result is False

    def test_context_ensures_app_on_enter(self, qapp):
        """验证进入弹窗上下文时会确保 QApplication 已存在。"""
        Popup.reset_instance()
        Popup._app = None

        with Popup.context():
            assert Popup._app is not None
            assert isinstance(Popup._app, QApplication)
