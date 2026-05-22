"""对话框辅助类单元测试。"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

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
        """验证默认账户标签重命名时全局配置自动同步。"""
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

    def test_auto_fill_from_folder_success(self, qapp, tmp_path):
        """验证文件夹中存在有效账户数据时，能正确提取并填充各字段。"""
        folder_path = tmp_path / "tdata_test"
        folder_path.mkdir()
        (folder_path / "key_datas").write_bytes(b"dummy_key")
        (folder_path / "D877F783D5D3EF8Cs").write_bytes(b"dummy_identity")
        maps_dir = folder_path / "D877F783D5D3EF8C"
        maps_dir.mkdir()
        (maps_dir / "maps").write_bytes(b"dummy_maps")
        (folder_path / "tas_tag").write_text("my_tag", encoding="utf-8")

        dialog = EditLabelDialog(parent=None)

        with patch('src.core.crypto_service.AccountDataCryptoService.decrypt_account_id', return_value="99999") as mock_decrypt:
            dialog.auto_fill_from_folder(str(folder_path))
            assert mock_decrypt.called
            assert Path(mock_decrypt.call_args[0][0]) == folder_path

        assert dialog.ui.user_id_edit.text() == "99999"
        assert dialog.ui.tag_edit.text() == "my_tag"

        import base64
        assert dialog._key == base64.b64encode(b"dummy_key").decode()
        assert dialog._identity == base64.b64encode(b"dummy_identity").decode()
        assert dialog._info == base64.b64encode(b"dummy_maps").decode()

    def test_auto_fill_from_folder_relative_path(self, qapp, tmp_path):
        """验证使用相对路径时，能通过父组件关联至基准路径并正确提取数据。"""
        from PySide6.QtWidgets import QWidget
        base_path = tmp_path / "telegram"
        base_path.mkdir()
        folder_path = base_path / "tdata_rel"
        folder_path.mkdir()
        (folder_path / "key_datas").write_bytes(b"dummy_key_rel")

        mock_parent = QWidget()
        mock_parent.ui = MagicMock()
        mock_parent.ui.path_edit = MagicMock()
        mock_parent.ui.path_edit.text.return_value = str(base_path)
        mock_parent.config = MagicMock()
        mock_parent.config.pwd = "my_pwd"

        dialog = EditLabelDialog(parent=mock_parent)

        with patch('src.core.crypto_service.AccountDataCryptoService.decrypt_account_id', return_value="111222") as mock_decrypt:
            dialog.auto_fill_from_folder("tdata_rel")
            assert mock_decrypt.called
            assert mock_decrypt.call_args[0][1] == "my_pwd"
            call_path = mock_decrypt.call_args[0][0]
            assert Path(call_path) == folder_path

        assert dialog.ui.user_id_edit.text() == "111222"
        import base64
        assert dialog._key == base64.b64encode(b"dummy_key_rel").decode()

    def test_auto_fill_from_folder_invalid_folder_ignored(self, qapp):
        """验证无效文件夹路径在自动填充时被安全忽略。"""
        dialog = EditLabelDialog(parent=None)
        dialog.auto_fill_from_folder("non_existent_folder_path_12345")
        assert dialog.ui.user_id_edit.text() == ""
        assert dialog._key == ""

