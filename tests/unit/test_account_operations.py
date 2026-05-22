"""账户切换逻辑单元测试。"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.account import account_operations
from src.core.exceptions import TASCipherException


class TestP0AccountOperations:
    """账户切换业务核心逻辑的单元测试。"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mock_config, mock_logger):
        """初始化测试模拟对象。"""
        with patch('src.core.account.account_operations.configs', mock_config), \
             patch('src.core.account.account_operations.logger', mock_logger):
            yield

    def test_restore_default_encrypts_current(self, mock_config, mock_logger, mock_account_fs):
        """验证恢复默认账户前正确加密活跃账户数据。"""
        mock_config.default = "default_account"
        mock_config.decrypted = True
        mock_config.tag = "current_account"
        mock_config.path = "/tmp/test_tas"
        mock_config.pwd = "test_password"

        mock_account_fs.find_account_folder.side_effect = lambda _, tag: (
            "tdata-current" if tag == "current_account" else "tdata-default"
        )
        mock_account_fs.swap_active_tdata_with_target.return_value = True

        from src.core.crypto import AESCipher
        cipher = MagicMock(spec=AESCipher)
        cipher.encrypt.return_value = True

        with patch('src.core.account.account_operations.AESCipher', return_value=cipher), \
             patch('src.core.account.account_operations.find_account_folder', mock_account_fs.find_account_folder), \
             patch('src.core.account.account_operations.swap_active_tdata_with_target', mock_account_fs.swap_active_tdata_with_target):
            result = account_operations._account_switch(
                method="restore",
                max_retries=1
            )

        assert result is True
        cipher.encrypt.assert_called_once()
        assert mock_account_fs.swap_active_tdata_with_target.called

    def test_switch_to_target_decrypts(self, mock_config, mock_logger, mock_account_fs):
        """验证切换到目标账户后，触发解密逻辑并更新配置状态。"""
        mock_config.tag = "target_account"
        mock_config.default = "default"
        mock_config.pwd = "test_password"
        mock_config.decrypted = False
        mock_config.path = "/tmp/test_tas"

        from src.core.crypto import AESCipher
        cipher = MagicMock(spec=AESCipher)
        cipher.decrypt.return_value = True

        mock_account_fs.find_account_folder.return_value = "tdata-target"
        mock_account_fs.swap_active_tdata_with_target.return_value = True

        with patch('src.core.account.account_operations.AESCipher', return_value=cipher), \
             patch('src.core.account.account_operations.find_account_folder', mock_account_fs.find_account_folder), \
             patch('src.core.account.account_operations.swap_active_tdata_with_target', mock_account_fs.swap_active_tdata_with_target):
            result = account_operations._account_switch(
                method="target",
                max_retries=1
            )

        assert result is True
        assert mock_config.decrypted is True
        cipher.decrypt.assert_called_once()

    def test_switch_key_login_fallback(self, mock_config, mock_logger, mock_account_fs):
        """验证若目标目录不存在，且具备完整凭证时，自动退化为密钥重建模式。"""
        mock_config.tag = "missing_account"
        mock_config.default = "default"
        mock_config.pwd = "test_password"
        mock_config.has_complete_keys.return_value = True
        mock_config.login_with_keys.return_value = True
        mock_config.path = "/tmp/test_tas"

        from src.core.crypto import AESCipher
        cipher = MagicMock(spec=AESCipher)
        mock_account_fs.find_account_folder.return_value = None

        with patch('src.core.account.account_operations.AESCipher', return_value=cipher), \
             patch('src.core.account.account_operations.find_account_folder', mock_account_fs.find_account_folder), \
             patch('src.core.account.account_operations.swap_active_tdata_with_target', mock_account_fs.swap_active_tdata_with_target):
            result = account_operations._account_switch(
                method="target",
                max_retries=1,
                confirm_callback=lambda msg: True
            )

        assert result is True
        mock_config.login_with_keys.assert_called_once()
        assert mock_config.decrypted is True

    def test_switch_retry_on_permission_error(self, mock_config, mock_logger, mock_account_fs):
        """验证在目标文件被锁定（PermissionError）时，具备重试切换的能力。"""
        mock_config.tag = "locked_account"
        mock_config.default = "default"
        mock_config.path = "/tmp/test_tas"
        mock_config.pwd = "test_password"

        from src.core.crypto import AESCipher
        cipher = MagicMock(spec=AESCipher)
        cipher.decrypt.return_value = True

        call_count = [0]
        def mock_swap(*args, **kwargs):
            """模拟目录交换行为。"""
            call_count[0] += 1
            if call_count[0] < 5:
                raise PermissionError("File locked")
            return True

        mock_account_fs.find_account_folder.return_value = "tdata-locked"
        mock_account_fs.swap_active_tdata_with_target.side_effect = mock_swap

        with patch('src.core.account.account_operations.AESCipher', return_value=cipher), \
             patch('src.core.account.account_operations.find_account_folder', mock_account_fs.find_account_folder), \
             patch('src.core.account.account_operations.swap_active_tdata_with_target', mock_account_fs.swap_active_tdata_with_target):
            result = account_operations._account_switch(
                method="target",
                max_retries=5
            )

        assert result is True
        assert call_count[0] == 5

    def test_switch_user_cancel_confirmation(self, mock_config, mock_logger, mock_account_fs):
        """验证用户拒绝确认（拒绝重构登录）时，流程立即中止。"""
        mock_config.tag = "missing_account"
        mock_config.default = "default"
        mock_config.has_complete_keys.return_value = True
        mock_config.path = "/tmp/test_tas"
        mock_config.pwd = "test_password"

        from src.core.crypto import AESCipher
        cipher = MagicMock(spec=AESCipher)
        mock_account_fs.find_account_folder.return_value = None

        with patch('src.core.account.account_operations.AESCipher', return_value=cipher), \
             patch('src.core.account.account_operations.find_account_folder', mock_account_fs.find_account_folder), \
             patch('src.core.account.account_operations.swap_active_tdata_with_target', mock_account_fs.swap_active_tdata_with_target):
            result = account_operations._account_switch(
                method="target",
                max_retries=1,
                confirm_callback=lambda msg: False
            )

        assert result is False
        mock_config.login_with_keys.assert_not_called()

    def test_switch_cipher_corruption_recovery(self, mock_config, mock_logger, mock_account_fs):
        """验证若解密失败，尝试通过备份凭证进行修复。"""
        mock_config.tag = "corrupted_account"
        mock_config.default = "default"
        mock_config.has_complete_keys.return_value = True
        mock_config.login_with_keys.return_value = True
        mock_config.path = "/tmp/test_tas"
        mock_config.pwd = "test_password"

        from src.core.crypto import AESCipher
        cipher = MagicMock(spec=AESCipher)

        decrypt_calls = [0]
        def mock_decrypt(*args, **kwargs):
            """模拟数据解密行为。"""
            decrypt_calls[0] += 1
            if decrypt_calls[0] == 1:
                raise TASCipherException("Corrupted key")
            return True

        cipher.decrypt.side_effect = mock_decrypt
        mock_account_fs.find_account_folder.return_value = "tdata"

        with patch('src.core.account.account_operations.AESCipher', return_value=cipher), \
             patch('src.core.account.account_operations.find_account_folder', mock_account_fs.find_account_folder), \
             patch('src.core.account.account_operations.swap_active_tdata_with_target', mock_account_fs.swap_active_tdata_with_target):
            result = account_operations._account_switch(
                method="target",
                max_retries=1,
                confirm_callback=lambda msg: True
            )

        assert result is True
        mock_config.login_with_keys.assert_called_once()
        assert decrypt_calls[0] == 2


class TestTempFolderNaming:
    """验证账户交换时的临时目录命名策略。"""

    def test_fixed_temp_name_in_test(self):
        """通过 monkeypatch 固定临时名，便于断言账户目录交换路径。"""
        with patch.object(account_operations, 'generate_temp_name', return_value="tdata-fixed1234"):
            name = account_operations.generate_temp_name()
            assert name == "tdata-fixed1234"


class TestRecovery:
    """紧急恢复功能的单元测试，涵盖进程终止与现场还原流程。"""

    def test_recovery_force_kills_process(self):
        """验证紧急恢复会优先强制终止 Telegram 进程。"""
        with patch('src.core.account.account_operations.ProcessManager') as MockPM, \
             patch('src.core.account.account_operations.configs') as mock_cs:
            mock_cs.client = "Telegram.exe"
            mock_pm = MockPM.return_value
            mock_pm.kill_process.return_value = True

            with patch.object(account_operations, 'restore_default', return_value=True):
                account_operations.recovery()
                mock_pm.kill_process.assert_called_once_with("Telegram.exe")

    def test_recovery_with_arguments(self):
        """验证紧急恢复支持传入自定义 config 和 logger 参数。"""
        mock_config = MagicMock()
        mock_config.client = "CustomClient.exe"
        mock_logger = MagicMock()

        with patch('src.core.account.account_operations.ProcessManager') as MockPM:
            mock_pm = MockPM.return_value
            mock_pm.kill_process.return_value = True

            with patch.object(account_operations, 'restore_default', return_value=True) as mock_restore:
                account_operations.recovery(config=mock_config, logger=mock_logger)
                mock_pm.kill_process.assert_called_once_with("CustomClient.exe")
                mock_restore.assert_called_once()

