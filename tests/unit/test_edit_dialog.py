"""账户编辑对话框单元测试。"""
import os
from unittest.mock import patch

from src.ui.dialogs import EditLabelDialog

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestEditLabelDialog:
    """覆盖账户编辑对话框的主要交互路径。"""

    def test_validate_inputs_empty_tag_rejects(self, qapp):
        """验证标签为空时拒绝提交并提示用户。"""
        dialog = EditLabelDialog()
        dialog.ui.folder_edit.setText("valid_folder")
        dialog.ui.tag_edit.setText("")

        with patch('src.ui.popup.alert') as mock_alert:
            result = dialog.validate_inputs()
            assert result is False
            mock_alert.assert_called_once()

    def test_validate_inputs_empty_folder_rejects(self, qapp):
        """验证路径为空时拒绝提交并提示用户。"""
        dialog = EditLabelDialog()
        dialog.ui.folder_edit.setText("")
        dialog.ui.tag_edit.setText("valid_tag")

        with patch('src.ui.popup.alert') as mock_alert:
            result = dialog.validate_inputs()
            assert result is False
            mock_alert.assert_called_once()

    def test_validate_and_accept_on_valid(self, qapp):
        """验证输入有效时，对话框进入确认流程。"""
        dialog = EditLabelDialog()
        dialog.ui.folder_edit.setText("valid_folder")
        dialog.ui.tag_edit.setText("valid_tag")

        with patch.object(dialog, 'accept') as mock_accept:
            dialog.validate_and_accept()
            mock_accept.assert_called_once()

    def test_set_default_and_accept_sets_flag(self, qapp):
        """验证设置默认账户时会保留用户意图并确认提交。"""
        dialog = EditLabelDialog()
        dialog.ui.folder_edit.setText("valid_folder")
        dialog.ui.tag_edit.setText("valid_tag")
        assert dialog.is_default is False

        with patch.object(dialog, 'accept') as mock_accept:
            dialog.set_default_and_accept()
            assert dialog.is_default is True
            mock_accept.assert_called_once()

    def test_get_account_data_returns_all_fields(self, qapp):
        """验证对话框能完整导出账户配置字段。"""
        dialog = EditLabelDialog(
            user_id="12345",
            folder="test_folder",
            tag="test_tag",
            info="test_info",
            identity="test_identity",
            key="test_key"
        )

        id_val, path, info, identity, key, tag = dialog.get_account_data()

        assert id_val == "12345"
        assert path == "test_folder"
        assert info == "test_info"
        assert identity == "test_identity"
        assert key == "test_key"
        assert tag == "test_tag"
