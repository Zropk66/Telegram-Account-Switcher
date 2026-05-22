"""文件系统与恢复服务单元测试。"""
from pathlib import Path

from src.core.account.account_services import (
    find_account_folder,
    swap_active_tdata_with_target,
    AccountRecoveryService
)


class TestAccountFileSystemService:
    """验证账户文件系统服务的功能性与安全操作正确性。"""

    def test_find_account_by_tag(self, tmp_path):
        """验证是否能通过解析 `tas_tag` 文件内容精准定位对应文件夹。"""
        base_dir = tmp_path

        account1_dir = base_dir / "tdata-account1"
        account1_dir.mkdir()
        (account1_dir / "tas_tag").write_text("account1", encoding="utf-8")

        account2_dir = base_dir / "tdata-account2"
        account2_dir.mkdir()
        (account2_dir / "tas_tag").write_text("account2", encoding="utf-8")

        assert find_account_folder(str(base_dir), "account1") == "tdata-account1"
        assert find_account_folder(str(base_dir), "account2") == "tdata-account2"
        assert find_account_folder(str(base_dir), "non_existent") is None

    def test_swap_tdata_safe(self, tmp_path):
        """验证 `tdata` 与目标目录的交换操作能否安全完成。"""
        base_dir = tmp_path

        tdata_dir = base_dir / "tdata"
        tdata_dir.mkdir()
        (tdata_dir / "tdata_file.txt").write_text("tdata content")

        target_dir = base_dir / "tdata-target"
        target_dir.mkdir()
        (target_dir / "target_file.txt").write_text("target content")

        temp_prefix = "tdata-temp123"
        result = swap_active_tdata_with_target(str(base_dir), "tdata-target", temp_prefix)

        assert result is True
        new_tdata = base_dir / "tdata"
        assert new_tdata.is_dir()
        assert (new_tdata / "target_file.txt").exists()
        assert not target_dir.exists()

    def test_swap_same_folder_returns_true(self, tmp_path):
        """验证目标已经是活跃目录时直接返回 True。"""
        base_dir = tmp_path

        tdata_dir = base_dir / "tdata"
        tdata_dir.mkdir()
        (tdata_dir / "test.txt").write_text("test")

        result = swap_active_tdata_with_target(str(base_dir), "tdata", "tdata-temp")

        assert result is True
        assert tdata_dir.exists()

    def test_swap_missing_tdata_returns_false(self, tmp_path):
        """验证原活跃目录不存在时仍能将目标提升为 tdata。"""
        base_dir = tmp_path

        target_dir = base_dir / "tdata-target"
        target_dir.mkdir()
        (target_dir / "target_file.txt").write_text("target content")

        result = swap_active_tdata_with_target(str(base_dir), "tdata-target", "tdata-temp")

        assert result is True
        new_tdata = base_dir / "tdata"
        assert new_tdata.is_dir()
        assert (new_tdata / "target_file.txt").exists()

    def test_swap_missing_target_returns_false(self, tmp_path):
        """验证若目标目录不存在，交换操作应被正确拒绝。"""
        base_dir = tmp_path

        tdata_dir = base_dir / "tdata"
        tdata_dir.mkdir()

        result = swap_active_tdata_with_target(str(base_dir), "non_existent", "tdata-temp")
        assert result is False


class TestAccountRecoveryService:
    """验证账户恢复服务在异常切换场景下的现场修复能力。"""

    def test_cleanup_orphan_restores_tdata(self, tmp_path, mock_logger):
        """验证程序崩溃后，能自动识别并恢复残留的临时目录。"""
        base_dir = tmp_path
        recovery = AccountRecoveryService(mock_logger)

        orphan_dir = base_dir / "tdata-abc123"
        orphan_dir.mkdir()
        (orphan_dir / "recovery_file.txt").write_text("recovery content")

        assert not (base_dir / "tdata").exists()

        recovery.cleanup_orphan_folders(str(base_dir))

        tdata_dir = base_dir / "tdata"
        assert tdata_dir.is_dir()
        assert (tdata_dir / "recovery_file.txt").exists()
        assert not orphan_dir.exists()
        mock_logger.warning.assert_called()

    def test_cleanup_no_orphan_does_nothing(self, tmp_path, mock_logger):
        """验证无残留时，清理逻辑不会对正常状态造成干扰。"""
        base_dir = tmp_path
        recovery = AccountRecoveryService(mock_logger)

        tdata_dir = base_dir / "tdata"
        tdata_dir.mkdir()
        (tdata_dir / "normal.txt").write_text("normal")

        recovery.cleanup_orphan_folders(str(base_dir))

        assert tdata_dir.exists()
        mock_logger.warning.assert_not_called()

    def test_cleanup_multiple_orphans_restores_first(self, tmp_path, mock_logger):
        """验证存在多个残留时仅修复首个发现的条目。"""
        base_dir = tmp_path
        recovery = AccountRecoveryService(mock_logger)

        orphan1 = base_dir / "tdata-first"
        orphan1.mkdir()
        (orphan1 / "file1.txt").write_text("first")

        orphan2 = base_dir / "tdata-second"
        orphan2.mkdir()
        (orphan2 / "file2.txt").write_text("second")

        recovery.cleanup_orphan_folders(str(base_dir))

        tdata_dir = base_dir / "tdata"
        assert tdata_dir.is_dir()
        assert (tdata_dir / "file1.txt").exists()
        assert orphan2.exists()

    def test_cleanup_empty_path_does_nothing(self, mock_logger):
        """验证非法路径输入不触发清理动作。"""
        recovery = AccountRecoveryService(mock_logger)
        recovery.cleanup_orphan_folders("")
        mock_logger.warning.assert_not_called()

    def test_cleanup_invalid_path_does_nothing(self, mock_logger):
        """验证不存在的路径输入不触发清理动作。"""
        recovery = AccountRecoveryService(mock_logger)
        recovery.cleanup_orphan_folders("/non/existent/path")
        mock_logger.warning.assert_not_called()

    def test_recover_account_success(self, mock_logger, mock_config):
        """验证基于备份凭证的账户重建流程成功。"""
        recovery = AccountRecoveryService(mock_logger)
        mock_config.get_account.return_value = {"folder": "tdata-test"}
        mock_config.path = "/tmp/path"
        mock_config.login_with_keys.return_value = True

        result = recovery.recover_account("test_tag", mock_config)

        assert result is True
        mock_config.get_account.assert_called_with("test_tag")
        mock_config.login_with_keys.assert_called()

    def test_recover_account_no_folder(self, mock_logger, mock_config):
        """验证凭证配置缺失时，恢复操作应被拒绝。"""
        recovery = AccountRecoveryService(mock_logger)
        mock_config.get_account.return_value = {"id": "123"}
        result = recovery.recover_account("test_tag", mock_config)

        assert result is False
        mock_config.login_with_keys.assert_not_called()

    def test_recover_account_login_failed(self, mock_logger, mock_config):
        """验证凭证校验不通过时，恢复操作应标记为失败。"""
        recovery = AccountRecoveryService(mock_logger)
        mock_config.get_account.return_value = {"folder": "tdata-test"}
        mock_config.path = "/tmp/path"
        mock_config.login_with_keys.return_value = False

        result = recovery.recover_account("test_tag", mock_config)

        assert result is False

    def test_get_key_datas_path(self, tmp_path):
        """验证获取账户明文数据文件路径的逻辑。"""
        folder = Path(tmp_path) / "test_folder"
        from src.core.account.account_services import get_key_datas_path
        result = get_key_datas_path(folder)
        assert result == folder / "key_datas"
