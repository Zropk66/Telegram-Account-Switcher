"""
账户切换集成测试。

验证账户切换主流程中配置、进程控制、文件交换和恢复服务之间的协作行为。
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.core.account.account_switcher import AccountSwitcher
from src.core.account.account_operations import switch_to_tag
from src.core.account.account_services import AccountRecoveryService


class TestIntegrationAccountSwitch:
    """覆盖账户切换的端到端关键路径。"""

    def test_full_switch_a_to_b_to_a(self, mock_config, mock_logger, mock_process_manager, mock_account_fs):
        """验证账户 A → B → A 的完整切换循环。"""
        mock_config.tags = {
            "account_a": {"id": "a123", "folder": "tdata-account_a", "info": "", "identity": "", "key": ""},
            "account_b": {"id": "b456", "folder": "tdata-account_b", "info": "", "identity": "", "key": ""}
        }
        mock_config.default = "account_a"

        with patch('src.core.account.account_switcher.ConfigService', return_value=mock_config), \
             patch('src.core.account.account_switcher.Logger', return_value=mock_logger), \
             patch('src.core.account.account_switcher.ProcessManager', return_value=mock_process_manager):
            switcher = AccountSwitcher()

            with patch('src.core.account.account_switcher.switch_to_tag') as mock_switch:
                mock_switch.return_value = True
                mock_config.tag = "account_b"

                result = switcher.process()

                assert result is True
                mock_switch.assert_called_once()

            with patch('src.core.account.account_switcher.restore_default') as mock_restore:
                mock_config.tag = "account_a"

                result = switcher.process()

                assert result is True
                mock_restore.assert_called_once()

            assert mock_process_manager.start_process.call_count == 2

    def test_encrypted_account_switch(self, mock_config, mock_logger, mock_process_manager, mock_account_fs):
        """验证加密账户切换会走文件交换与加解密协作路径。"""
        mock_config.tags = {
            "account_a": {"id": "a123", "folder": "tdata-account_a", "info": "", "identity": "", "key": ""},
            "account_b": {"id": "b456", "folder": "tdata-account_b", "info": "", "identity": "", "key": ""}
        }
        mock_config.default = "account_a"
        mock_config.tag = "account_b"
        mock_config.decrypted = True
        mock_config.pwd = "test_password"

        mock_cipher = MagicMock()
        mock_cipher.is_encrypted.return_value = False

        with patch('src.core.account.account_operations.AESCipher', return_value=mock_cipher), \
             patch('src.core.account.account_operations.find_account_folder', mock_account_fs.find_account_folder), \
             patch('src.core.account.account_operations.swap_active_tdata_with_target', mock_account_fs.swap_active_tdata_with_target):

            switch_to_tag(max_retries=1, confirm_callback=None)

            mock_account_fs.swap_active_tdata_with_target.assert_called_once()

    def test_crash_recovery_interrupted_switch(self, mock_config, mock_logger, temp_dir):
        """验证切换中断后，恢复服务会识别并处理孤立临时目录。"""
        recovery_service = AccountRecoveryService(mock_logger)
        mock_config.path = str(temp_dir)

        tdata_path = temp_dir / "tdata"
        temp_folder = temp_dir / "tdata-temp-1"
        temp_folder.mkdir(parents=True, exist_ok=True)

        assert not tdata_path.exists()
        assert temp_folder.exists()

        with patch('pathlib.Path.rename'):
            recovery_service.cleanup_orphan_folders(str(temp_dir))

            mock_logger.warning.assert_called()

    def test_concurrent_switch_prevention(self, mock_config, mock_logger, mock_process_manager):
        """验证切换会话能统一管理进程守护和孤立目录清理。"""
        with patch('src.core.account.account_switcher.ConfigService', return_value=mock_config), \
             patch('src.core.account.account_switcher.Logger', return_value=mock_logger), \
             patch('src.core.account.account_switcher.ProcessManager', return_value=mock_process_manager):
            switcher = AccountSwitcher()

            session_active = False

            with patch('src.core.account.account_switcher.restore_default'):
                with switcher.switching_session():
                    session_active = True
                    mock_process_manager.kill_called = True

                assert session_active is True

            with patch.object(switcher._recovery_service, 'cleanup_orphan_folders') as mock_cleanup:
                with switcher.switching_session():
                    pass
                mock_cleanup.assert_called_once_with(mock_config.path)

    def test_account_switcher_switching_session_rollback(self, mock_config, mock_logger, mock_process_manager):
        """验证切换会话异常退出时会触发默认账户回滚。"""
        with patch('src.core.account.account_switcher.ConfigService', return_value=mock_config), \
             patch('src.core.account.account_switcher.Logger', return_value=mock_logger), \
             patch('src.core.account.account_switcher.ProcessManager', return_value=mock_process_manager):
            switcher = AccountSwitcher()

            with patch('src.core.account.account_switcher.restore_default') as mock_restore:
                with pytest.raises(Exception, match="测试异常"):
                    with switcher.switching_session():
                        raise Exception("测试异常")

                mock_restore.assert_called_once()
                mock_logger.error.assert_called_once()

    def test_account_switcher_with_recovery_service(self, mock_config, mock_logger, mock_process_manager):
        """验证自定义恢复服务会参与切换前的现场清理。"""
        mock_recovery = MagicMock()

        with patch('src.core.account.account_switcher.ConfigService', return_value=mock_config), \
             patch('src.core.account.account_switcher.Logger', return_value=mock_logger), \
             patch('src.core.account.account_switcher.ProcessManager', return_value=mock_process_manager), \
             patch('src.core.account.account_switcher.AccountRecoveryService', return_value=mock_recovery):
            switcher = AccountSwitcher()

            with patch('src.core.account.account_switcher.switch_to_tag', return_value=True), \
                 patch('src.core.account.account_switcher.AccountMonitor'):
                mock_config.tag = "test_account"
                mock_config.tags = {"test_account": {"id": "123", "folder": "tdata-test"}}

                switcher.process()

                mock_recovery.cleanup_orphan_folders.assert_called_once_with(mock_config.path)

    def test_recover_account_from_backup_keys(self, mock_config, mock_logger):
        """验证账户可通过备份密钥恢复登录文件。"""
        recovery_service = AccountRecoveryService(mock_logger)

        test_tag = "test_account"
        mock_config.get_account.return_value = {"folder": "tdata-test"}
        mock_config.login_with_keys.return_value = True

        result = recovery_service.recover_account(test_tag, mock_config)

        assert result is True
        mock_config.login_with_keys.assert_called_once_with(test_tag, str(Path(mock_config.path) / "tdata-test"))
        mock_logger.warning.assert_called_once()
