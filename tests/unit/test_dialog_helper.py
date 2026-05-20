"""
SettingsDialogHelper 单元测试。

验证设置对话框辅助类的核心业务逻辑，包括对话框结果处理、配置持久化同步及账户文件系统联动。
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# 设置 offscreen 模式，避免单元测试依赖真实显示器环境
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtCore import Qt

from src.ui.dialogs import SettingsDialogHelper, EditLabelDialog


class TestSettingsDialogHelper:
    """
    验证 SettingsDialogHelper 类处理对话框交互的正确性。
    """

    def test_handle_result_updates_existing_item(self, tmp_path):
        """验证编辑现有账户时，正确更新对应的列表条目数据。"""
        mock_item = MagicMock()
        mock_item.data.return_value = {'tag': 'old_tag', 'id': '123', 'folder': 'old_folder'}

        mock_dialog = MagicMock(spec=EditLabelDialog)
        mock_dialog.is_default = False
        mock_dialog.get_account_data.return_value = ('456', 'new_folder', 'new_info', 'new_identity', 'new_key', 'new_tag')

        current_configs = {'default': 'some_tag'}

        update_cb = MagicMock()
        model_update_cb = MagicMock()
        model_add_cb = MagicMock()

        SettingsDialogHelper.handle_edit_dialog_result(
            item=mock_item,
            dialog=mock_dialog,
            current_configs=current_configs,
            path_edit_text=str(tmp_path),
            update_config_callback=update_cb,
            model_update_callback=model_update_cb,
            model_add_callback=model_add_cb,
            config_manage=None,
            refresh_display_callback=None
        )

        expected_data = {
            'tag': 'new_tag',
            'id': '456',
            'folder': 'new_folder',
            'info': 'new_info',
            'identity': 'new_identity',
            'key': 'new_key'
        }

        model_update_cb.assert_called_once_with(mock_item, expected_data)
        model_add_cb.assert_not_called()

    def test_handle_result_adds_new_item(self, tmp_path):
        """验证新增账户时，正确调用模型添加回调。"""
        mock_dialog = MagicMock(spec=EditLabelDialog)
        mock_dialog.is_default = False
        mock_dialog.get_account_data.return_value = ('123', 'new_folder', 'info', 'identity', 'key', 'new_tag')

        current_configs = {'default': 'some_tag'}

        update_cb = MagicMock()
        model_update_cb = MagicMock()
        model_add_cb = MagicMock()

        SettingsDialogHelper.handle_edit_dialog_result(
            item=None,
            dialog=mock_dialog,
            current_configs=current_configs,
            path_edit_text=str(tmp_path),
            update_config_callback=update_cb,
            model_update_callback=model_update_cb,
            model_add_callback=model_add_cb,
            config_manage=None,
            refresh_display_callback=None
        )

        expected_data = {
            'tag': 'new_tag',
            'id': '123',
            'folder': 'new_folder',
            'info': 'info',
            'identity': 'identity',
            'key': 'key'
        }

        model_add_cb.assert_called_once_with(expected_data)
        model_update_cb.assert_not_called()

    def test_handle_result_sets_default_on_flag(self, tmp_path):
        """验证设置为默认账户时，配置中心及 UI 同步更新状态。"""
        mock_dialog = MagicMock(spec=EditLabelDialog)
        mock_dialog.is_default = True
        mock_dialog.get_account_data.return_value = ('123', 'folder', 'info', 'identity', 'key', 'new_tag')

        current_configs = {'default': 'old_default'}
        mock_config_manage = MagicMock()

        update_cb = MagicMock()
        model_update_cb = MagicMock()
        model_add_cb = MagicMock()
        refresh_cb = MagicMock()

        SettingsDialogHelper.handle_edit_dialog_result(
            item=None,
            dialog=mock_dialog,
            current_configs=current_configs,
            path_edit_text=str(tmp_path),
            update_config_callback=update_cb,
            model_update_callback=model_update_cb,
            model_add_callback=model_add_cb,
            config_manage=mock_config_manage,
            refresh_display_callback=refresh_cb
        )

        assert mock_config_manage.default == 'new_tag'
        update_cb.assert_any_call('default', 'new_tag')
        refresh_cb.assert_called_once_with('new_tag')

    def test_handle_result_writes_tag_file(self, tmp_path):
        """验证保存配置时会自动生成并写入账户标识文件 tas_tag。"""
        base_path = tmp_path / "telegram"
        base_path.mkdir()

        mock_dialog = MagicMock(spec=EditLabelDialog)
        mock_dialog.is_default = False
        folder_name = "tdata-test"
        mock_dialog.get_account_data.return_value = ('123', folder_name, 'info', 'identity', 'key', 'my_test_tag')

        current_configs = {'default': 'some_tag'}

        update_cb = MagicMock()
        model_update_cb = MagicMock()
        model_add_cb = MagicMock()

        SettingsDialogHelper.handle_edit_dialog_result(
            item=None,
            dialog=mock_dialog,
            current_configs=current_configs,
            path_edit_text=str(base_path),
            update_config_callback=update_cb,
            model_update_callback=model_update_cb,
            model_add_callback=model_add_cb,
            config_manage=None,
            refresh_display_callback=None
        )

        expected_folder = base_path / folder_name
        assert expected_folder.exists()

        tag_file = expected_folder / "tas_tag"
        assert tag_file.exists()
        assert tag_file.read_text(encoding="utf-8") == "my_test_tag"

    def test_handle_result_updates_default_when_tag_changed(self, tmp_path):
        """验证当默认账户的标签名被重命名时，全局配置会自动同步。"""
        mock_item = MagicMock()
        mock_item.data.return_value = {'tag': 'old_default_tag', 'id': '123', 'folder': 'folder'}

        mock_dialog = MagicMock(spec=EditLabelDialog)
        mock_dialog.is_default = False
        mock_dialog.get_account_data.return_value = ('123', 'folder', 'info', 'identity', 'key', 'new_default_tag')

        current_configs = {'default': 'old_default_tag'}

        update_cb = MagicMock()
        model_update_cb = MagicMock()
        model_add_cb = MagicMock()

        SettingsDialogHelper.handle_edit_dialog_result(
            item=mock_item,
            dialog=mock_dialog,
            current_configs=current_configs,
            path_edit_text=str(tmp_path),
            update_config_callback=update_cb,
            model_update_callback=model_update_cb,
            model_add_callback=model_add_cb,
            config_manage=None,
            refresh_display_callback=None
        )

        update_cb.assert_any_call('default', 'new_default_tag')
