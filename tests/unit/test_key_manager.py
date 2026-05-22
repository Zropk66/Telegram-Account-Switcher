"""密钥管理单元测试。"""
import base64
from unittest.mock import MagicMock

import pytest

from src.core.config.config import PathConfig
from src.core.config.key_manager import TelegramKeyManager


class TestTelegramKeyManager:
    """覆盖账户密钥备份与密钥登录的关键文件操作路径。"""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """提供隔离文件系统操作的临时目录。"""
        return tmp_path

    @pytest.fixture
    def mock_config_service(self):
        """提供配置服务替身。"""
        config = MagicMock()
        config.get_account.return_value = {}
        return config

    def test_backup_keys_encodes_base64(self, temp_dir, mock_config_service):
        """验证密钥文件备份时以 base64 文本形式写入配置。"""
        account_folder = temp_dir / 'tdata-test'
        account_folder.mkdir()

        identity_path = account_folder / PathConfig.IDENTITY_FOLDER
        info_path = account_folder / 'D877F783D5D3EF8C' / PathConfig.INFO_SUBFOLDER
        key_path = account_folder / PathConfig.KEY_FOLDER

        identity_path.parent.mkdir(parents=True, exist_ok=True)
        info_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.parent.mkdir(parents=True, exist_ok=True)

        identity_data = b'test_identity_data'
        info_data = b'test_info_data'
        key_data = b'test_key_data'

        identity_path.write_bytes(identity_data)
        info_path.write_bytes(info_data)
        key_path.write_bytes(key_data)

        account_data = {"id": "12345", "folder": "tdata-test"}
        mock_config_service.get_account.return_value = account_data

        result = TelegramKeyManager.backup_keys("test_tag", account_folder, mock_config_service)

        assert result is True
        mock_config_service.get_account.assert_called_once_with("test_tag")
        mock_config_service.set_account.assert_called_once()

        saved_data = mock_config_service.set_account.call_args[0][1]
        assert 'info' in saved_data
        assert 'identity' in saved_data
        assert 'key' in saved_data

        assert isinstance(saved_data['info'], str)
        assert isinstance(saved_data['identity'], str)
        assert isinstance(saved_data['key'], str)
        assert base64.b64decode(saved_data['info']) == info_data
        assert base64.b64decode(saved_data['identity']) == identity_data
        assert base64.b64decode(saved_data['key']) == key_data

    def test_backup_missing_key_file_returns_false(self, temp_dir, mock_config_service):
        """验证密钥文件缺失时拒绝生成不完整备份。"""
        account_folder = temp_dir / 'tdata-missing'
        account_folder.mkdir()

        identity_path = account_folder / PathConfig.IDENTITY_FOLDER
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        identity_path.write_bytes(b'data')

        result = TelegramKeyManager.backup_keys("test_tag", account_folder, mock_config_service)

        assert result is False
        mock_config_service.set_account.assert_not_called()

    def test_login_with_keys_restores_files(self, temp_dir, mock_config_service):
        """验证完整备份密钥能恢复为 Telegram 期望的本地文件结构。"""
        test_identity_data = b'restored_identity'
        test_info_data = b'restored_info'
        test_key_data = b'restored_key'

        test_identity = base64.b64encode(test_identity_data).decode()
        test_info = base64.b64encode(test_info_data).decode()
        test_key = base64.b64encode(test_key_data).decode()

        account_data = {
            'identity': test_identity,
            'info': test_info,
            'key': test_key
        }

        mock_config_service.has_complete_keys.return_value = True
        mock_config_service.get_account.return_value = account_data

        tdata_path = temp_dir / 'tdata_target'
        tdata_path.mkdir(parents=True)

        result = TelegramKeyManager.login_with_keys("test_tag", str(tdata_path), mock_config_service)

        assert result is True
        mock_config_service.has_complete_keys.assert_called_once_with("test_tag")
        mock_config_service.get_account.assert_called_once_with("test_tag")

        identity_path = tdata_path / PathConfig.IDENTITY_FOLDER
        info_path = tdata_path / 'D877F783D5D3EF8C' / PathConfig.INFO_SUBFOLDER
        key_path = tdata_path / PathConfig.KEY_FOLDER

        assert identity_path.exists()
        assert info_path.exists()
        assert key_path.exists()

        assert identity_path.read_bytes() == test_identity_data
        assert info_path.read_bytes() == test_info_data
        assert key_path.read_bytes() == test_key_data

    def test_login_incomplete_keys_returns_false(self, temp_dir, mock_config_service):
        """验证不完整密钥无法进入登录恢复流程。"""
        mock_config_service.has_complete_keys.return_value = False
        result = TelegramKeyManager.login_with_keys("test_tag", str(temp_dir), mock_config_service)
        assert result is False

        mock_config_service.has_complete_keys.return_value = True
        mock_config_service.get_account.return_value = {
            'identity': base64.b64encode(b'data').decode(),
        }
        result = TelegramKeyManager.login_with_keys("test_tag", str(temp_dir), mock_config_service)
        assert result is False

        mock_config_service.get_account.return_value = {
            'identity': '',
            'info': base64.b64encode(b'data').decode(),
            'key': base64.b64encode(b'data').decode()
        }
        result = TelegramKeyManager.login_with_keys("test_tag", str(temp_dir), mock_config_service)
        assert result is False
