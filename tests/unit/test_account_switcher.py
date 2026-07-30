"""账户切换器单元测试。"""
from unittest.mock import MagicMock, patch

import pytest

from src.core.account.account_switcher import AccountSwitcher


class TestAccountSwitcher:
    """覆盖账户切换协调器的核心控制流。"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mock_config, mock_logger, mock_process_manager):
        """初始化测试模拟对象。"""
        with patch('src.core.account.account_switcher.ConfigService', return_value=mock_config), \
             patch('src.core.account.account_switcher.Logger', return_value=mock_logger), \
             patch('src.core.account.account_switcher.ProcessManager', return_value=mock_process_manager):
            yield

    def test_switching_session_exception_rollback(self, mock_config, mock_logger):
        """验证切换过程中异常会触发默认账户回滚。"""
        switcher = AccountSwitcher()

        with patch('src.core.account.account_switcher.restore_default') as mock_restore_default:
            with pytest.raises(Exception, match="测试异常"):
                with switcher.switching_session():
                    raise Exception("测试异常")

            mock_restore_default.assert_called_once()
            mock_logger.error.assert_called()

    def test_process_default_account_fast_path(self, mock_config, mock_process_manager):
        """验证目标为默认账户时直接恢复默认 tdata 并启动客户端。"""
        mock_config.tag = mock_config.default
        mock_config.tags = {}

        switcher = AccountSwitcher()

        with patch('src.core.account.account_switcher.restore_default') as mock_restore_default, \
             patch('src.core.account.account_switcher.AccountMonitor'):

            result = switcher.process()

            assert result is True
            mock_restore_default.assert_called_once()
            mock_process_manager.start_process.assert_called_once_with(wait=True, tdata_name='tdata-abc')
            mock_config.sync_all_account_paths.assert_called_once()

    def test_process_target_full_flow(self, mock_config, mock_process_manager):
        """验证目标账户的完整切换流程会按顺序执行。"""
        test_tag = "account1"
        mock_config.tag = test_tag
        mock_config.tags = {test_tag: {"id": "12345", "folder": "tdata-abc"}}
        mock_config.default = "default_account"

        switcher = AccountSwitcher()

        with patch('src.core.account.account_switcher.switch_to_tag', return_value=True) as mock_switch_to_tag, \
             patch('src.core.account.account_switcher.AccountMonitor'):

            result = switcher.process()

            assert result is True
            mock_switch_to_tag.assert_called_once()
            mock_process_manager.start_process.assert_called_once_with(wait=True)
            mock_config.sync_all_account_paths.assert_called_once()

    def test_process_target_failed(self, mock_config, mock_process_manager):
        """验证目标账户切换失败时不会继续启动客户端。"""
        test_tag = "account1"
        mock_config.tag = test_tag
        mock_config.tags = {test_tag: {"id": "12345", "folder": "tdata-abc"}}
        mock_config.default = "default_account"

        switcher = AccountSwitcher()

        with patch('src.core.account.account_switcher.switch_to_tag', return_value=False) as mock_switch_to_tag, \
             patch('src.core.account.account_switcher.AccountMonitor'):

            result = switcher.process()

            assert result is False
            mock_switch_to_tag.assert_called_once()
            mock_process_manager.start_process.assert_not_called()

    def test_monitor_started_on_success(self, mock_config, mock_logger):
        """验证切换成功后会创建后台账户监控实例。"""
        mock_config.tag = mock_config.default
        mock_config.tags = {}

        switcher = AccountSwitcher()

        monitor_instance = MagicMock()

        with patch('src.core.account.account_switcher.AccountMonitor', return_value=monitor_instance) as mock_monitor_class, \
             patch('src.core.account.account_switcher.restore_default'):

            result = switcher.process()

            mock_monitor_class.assert_called_once()
            assert result is True
            assert switcher.monitor is monitor_instance

    def test_recover_account_on_failure_with_keys(self, mock_config, mock_process_manager):
        """验证启动失败且具备完整密钥时会尝试恢复账户。"""
        test_tag = "account1"
        mock_config.tag = test_tag
        mock_config.tags = {test_tag: {"id": "12345", "folder": "tdata-abc"}}
        mock_config.default = "other_account"
        mock_config.has_complete_keys.return_value = True
        mock_config.decrypted = False
        mock_process_manager.start_process.return_value = False

        mock_recovery_service = MagicMock()

        switcher = AccountSwitcher()
        switcher._recovery_service = mock_recovery_service

        from contextlib import contextmanager

        @contextmanager
        def mock_kill_and_guard(client_name, restart_on_exit=False):
            """模拟守护进程。"""
            yield

        mock_process_manager.kill_and_guard = mock_kill_and_guard

        with patch('src.core.account.account_switcher.switch_to_tag', return_value=True):
            result = switcher.process()

            assert result is False
            mock_recovery_service.recover_account.assert_called_once_with(test_tag, mock_config)

    def test_no_recovery_without_keys(self, mock_config, mock_process_manager):
        """验证缺少完整密钥时，启动失败不会进入恢复流程。"""
        test_tag = "account1"
        mock_config.tag = test_tag
        mock_config.tags = {test_tag: {"id": "12345", "folder": "tdata-abc"}}
        mock_config.has_complete_keys.return_value = False
        mock_process_manager.start_process.return_value = False

        switcher = AccountSwitcher()

        mock_recovery_service = MagicMock()
        switcher._recovery_service = mock_recovery_service

        with patch('src.core.account.account_switcher.switch_to_tag', return_value=True):
            result = switcher.process()

            assert result is False
            mock_recovery_service.recover_account.assert_not_called()

    def test_process_exception_triggers_rollback(self, mock_config, mock_process_manager):
        """验证 process 执行中发生异常时，确实触发了默认账户回滚并返回 False。"""
        test_tag = "account1"
        mock_config.tag = test_tag
        mock_config.tags = {test_tag: {"id": "12345", "folder": "tdata-abc"}}
        mock_config.default = "default_account"

        switcher = AccountSwitcher()

        with patch.object(switcher, '_process', side_effect=Exception("切换异常")), \
             patch.object(switcher, '_rollback_to_default') as mock_rollback:
            result = switcher.process()

            assert result is False
            mock_rollback.assert_called_once()

    def test_rollback_to_default_calls_restore(self, mock_config):
        """验证回滚仅调用 restore_default，不执行数据移动。"""
        mock_config.path = "/tmp/test_tas"
        mock_config.default = "default_account"

        switcher = AccountSwitcher()

        from pathlib import Path
        with patch('src.core.account.account_switcher.restore_default') as mock_restore_default, \
             patch.object(Path, 'rename') as mock_rename:

            switcher._rollback_to_default(actual_default_folder="tdata-default")

            mock_rename.assert_not_called()
            mock_restore_default.assert_called_once_with(target_folder="tdata-default")

    def test_rollback_to_default_none_folder(self, mock_config):
        """验证缺失默认目录时以 None 调用恢复默认。"""
        mock_config.path = "/tmp/test_tas"
        mock_config.default = "default_account"

        switcher = AccountSwitcher()

        from pathlib import Path
        with patch('src.core.account.account_switcher.restore_default') as mock_restore_default, \
             patch.object(Path, 'rename') as mock_rename:

            switcher._rollback_to_default(actual_default_folder=None)

            mock_rename.assert_not_called()
            mock_restore_default.assert_called_once_with(target_folder=None)

    def test_rollback_no_backup_rename(self, mock_config):
        """验证软链接模式下回滚不执行任何备份重命名操作。"""
        mock_config.path = "/tmp/test_tas"
        mock_config.default = "default_account"

        switcher = AccountSwitcher()

        from pathlib import Path
        with patch('src.core.account.account_switcher.restore_default') as mock_restore_default, \
             patch.object(Path, 'rename') as mock_rename, \
             patch('shutil.rmtree') as mock_rmtree:

            switcher._rollback_to_default(actual_default_folder="tdata-default")

            mock_rename.assert_not_called()
            mock_rmtree.assert_not_called()
            mock_restore_default.assert_called_once_with(target_folder="tdata-default")

    def test_hook_mode_fallback_disabled(self, mock_config, mock_process_manager):
        """验证禁用 fallback 时，hook 模式启动失败不会触发降级处理。"""
        from src.core.constants import LaunchMode

        test_tag = "account1"
        mock_config.tag = test_tag
        mock_config.tags = {test_tag: {"id": "12345", "folder": "tdata-abc"}}
        mock_config.default = "default_account"
        mock_config.launch_mode = LaunchMode.HOOK
        mock_config.hook_fallback = False
        mock_config.has_complete_keys.return_value = False
        mock_process_manager.start_process.return_value = False

        switcher = AccountSwitcher()
        try:
            with patch.object(switcher, '_fallback_to_symlink') as mock_fallback:
                result = switcher.process()
                assert result is False
                mock_fallback.assert_not_called()
        finally:
            from src.core.config import ConfigService
            ConfigService.reset_instance()
