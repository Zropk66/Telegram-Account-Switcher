"""文件系统与恢复服务单元测试。"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.account.account_services import (
    find_account_folder,
    repoint_tdata_link,
    is_tdata_link,
    get_tdata_link_target,
    remove_tdata_link,
    AccountRecoveryService,
)


def _can_symlink(tmp_path):
    """检测当前环境是否支持创建软链接。"""
    target = tmp_path / "probe_target"
    link = tmp_path / "probe_link"
    target.mkdir()
    try:
        os.symlink("probe_target", str(link), target_is_directory=True)
        link.unlink()
        return True
    except (OSError, NotImplementedError):
        return False


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

    def test_find_account_skips_symlink(self, tmp_path):
        """验证 find_account_folder 跳过软链接，不将 tdata 链接识别为账户目录。"""
        if not _can_symlink(tmp_path):
            pytest.skip("当前环境不支持软链接")

        base_dir = tmp_path

        account_dir = base_dir / "tdata-account1"
        account_dir.mkdir()
        (account_dir / "tas_tag").write_text("account1", encoding="utf-8")

        tdata_link = base_dir / "tdata"
        os.symlink("tdata-account1", str(tdata_link), target_is_directory=True)

        result = find_account_folder(str(base_dir), "account1")
        assert result == "tdata-account1"

    def test_repoint_creates_new_link(self, tmp_path):
        """验证 tdata 不存在时创建新软链接。"""
        base_dir = tmp_path
        target_dir = base_dir / "tdata-target"
        target_dir.mkdir()

        with patch('src.core.account.account_services.os.symlink') as mock_symlink:
            result = repoint_tdata_link(str(base_dir), "tdata-target")

        assert result is True
        mock_symlink.assert_called_once_with(
            "tdata-target", str(base_dir / "tdata"), target_is_directory=True
        )

    def test_repoint_already_pointing_to_target(self, tmp_path):
        """验证已指向目标时直接返回 True（无操作）。"""
        if not _can_symlink(tmp_path):
            pytest.skip("当前环境不支持软链接")

        base_dir = tmp_path
        target_dir = base_dir / "tdata-target"
        target_dir.mkdir()

        tdata_link = base_dir / "tdata"
        os.symlink("tdata-target", str(tdata_link), target_is_directory=True)

        with patch('src.core.account.account_services.os.symlink') as mock_symlink:
            result = repoint_tdata_link(str(base_dir), "tdata-target")

        assert result is True
        mock_symlink.assert_not_called()

    def test_repoint_removes_old_link_and_creates_new(self, tmp_path):
        """验证已有链接指向其他目标时移除旧链接并创建新链接。"""
        if not _can_symlink(tmp_path):
            pytest.skip("当前环境不支持软链接")

        base_dir = tmp_path
        other_dir = base_dir / "tdata-other"
        other_dir.mkdir()
        target_dir = base_dir / "tdata-target"
        target_dir.mkdir()

        tdata_link = base_dir / "tdata"
        os.symlink("tdata-other", str(tdata_link), target_is_directory=True)

        with patch('src.core.account.account_services.os.symlink') as mock_symlink:
            result = repoint_tdata_link(str(base_dir), "tdata-target")

        assert result is True
        mock_symlink.assert_called_once_with(
            "tdata-target", str(base_dir / "tdata"), target_is_directory=True
        )
        assert not tdata_link.is_symlink() or get_tdata_link_target(str(base_dir)) == "tdata-target"

    def test_repoint_target_not_exist_returns_false(self, tmp_path):
        """验证目标目录不存在时返回 False。"""
        result = repoint_tdata_link(str(tmp_path), "non_existent")
        assert result is False

    def test_repoint_migrates_real_tdata(self, tmp_path):
        """验证实体 tdata 目录会被迁移为账户目录后再创建链接。"""
        base_dir = tmp_path
        tdata_dir = base_dir / "tdata"
        tdata_dir.mkdir()
        (tdata_dir / "tas_tag").write_text("mytag", encoding="utf-8")

        target_dir = base_dir / "tdata-target"
        target_dir.mkdir()

        with patch('src.core.account.account_services.os.symlink') as mock_symlink:
            result = repoint_tdata_link(str(base_dir), "tdata-target")

        assert result is True
        assert (base_dir / "tdata-mytag").is_dir()
        mock_symlink.assert_called_once()

    def test_repoint_migrate_conflict_returns_false(self, tmp_path):
        """验证迁移目标已存在时返回 False。"""
        base_dir = tmp_path
        tdata_dir = base_dir / "tdata"
        tdata_dir.mkdir()
        (tdata_dir / "tas_tag").write_text("mytag", encoding="utf-8")

        conflict_dir = base_dir / "tdata-mytag"
        conflict_dir.mkdir()

        target_dir = base_dir / "tdata-target"
        target_dir.mkdir()

        result = repoint_tdata_link(str(base_dir), "tdata-target")
        assert result is False

    def test_is_tdata_link_true(self, tmp_path):
        """验证 tdata 为软链接时返回 True。"""
        if not _can_symlink(tmp_path):
            pytest.skip("当前环境不支持软链接")

        base_dir = tmp_path
        target = base_dir / "tdata-real"
        target.mkdir()
        os.symlink("tdata-real", str(base_dir / "tdata"), target_is_directory=True)

        assert is_tdata_link(str(base_dir)) is True

    def test_is_tdata_link_false(self, tmp_path):
        """验证 tdata 为实体目录或不存在时返回 False。"""
        base_dir = tmp_path
        assert is_tdata_link(str(base_dir)) is False

        (base_dir / "tdata").mkdir()
        assert is_tdata_link(str(base_dir)) is False

    def test_get_tdata_link_target(self, tmp_path):
        """验证获取 tdata 软链接指向的目标文件夹名。"""
        if not _can_symlink(tmp_path):
            pytest.skip("当前环境不支持软链接")

        base_dir = tmp_path
        target = base_dir / "tdata-account1"
        target.mkdir()
        os.symlink("tdata-account1", str(base_dir / "tdata"), target_is_directory=True)

        assert get_tdata_link_target(str(base_dir)) == "tdata-account1"

    def test_get_tdata_link_target_not_link(self, tmp_path):
        """验证 tdata 非软链接时返回 None。"""
        base_dir = tmp_path
        assert get_tdata_link_target(str(base_dir)) is None

        (base_dir / "tdata").mkdir()
        assert get_tdata_link_target(str(base_dir)) is None

    def test_remove_tdata_link(self, tmp_path):
        """验证移除 tdata 软链接不影响目标目录。"""
        if not _can_symlink(tmp_path):
            pytest.skip("当前环境不支持软链接")

        base_dir = tmp_path
        target = base_dir / "tdata-real"
        target.mkdir()
        (target / "file.txt").write_text("content")

        os.symlink("tdata-real", str(base_dir / "tdata"), target_is_directory=True)

        result = remove_tdata_link(str(base_dir))
        assert result is True
        assert not (base_dir / "tdata").exists()
        assert target.is_dir()
        assert (target / "file.txt").exists()

    def test_remove_tdata_link_no_link(self, tmp_path):
        """验证 tdata 不存在或非链接时返回 True（幂等）。"""
        base_dir = tmp_path
        assert remove_tdata_link(str(base_dir)) is True


class TestAccountRecoveryService:
    """验证账户恢复服务在异常切换场景下的现场修复能力。"""

    def test_cleanup_removes_broken_symlink(self, tmp_path, mock_logger):
        """验证失效的 tdata 软链接会被移除。"""
        if not _can_symlink(tmp_path):
            pytest.skip("当前环境不支持软链接")

        base_dir = tmp_path

        temp_target = base_dir / "tdata-temp-target"
        temp_target.mkdir()
        os.symlink("tdata-temp-target", str(base_dir / "tdata"), target_is_directory=True)
        temp_target.rmdir()

        recovery = AccountRecoveryService(mock_logger)
        recovery.cleanup_orphan_folders(str(base_dir))

        assert not (base_dir / "tdata").is_symlink()
        mock_logger.warning.assert_called()

    def test_cleanup_migrates_real_tdata(self, tmp_path, mock_logger):
        """验证实体 tdata 目录会被迁移为软链接。"""
        base_dir = tmp_path
        tdata_dir = base_dir / "tdata"
        tdata_dir.mkdir()
        (tdata_dir / "tas_tag").write_text("mytag", encoding="utf-8")

        recovery = AccountRecoveryService(mock_logger)
        with patch('src.core.account.account_services.os.symlink'):
            recovery.cleanup_orphan_folders(str(base_dir))

        assert (base_dir / "tdata-mytag").is_dir()
        mock_logger.warning.assert_called()

    def test_cleanup_no_tdata_does_nothing(self, tmp_path, mock_logger):
        """验证无 tdata 时不触发清理动作。"""
        recovery = AccountRecoveryService(mock_logger)
        recovery.cleanup_orphan_folders(str(tmp_path))
        mock_logger.warning.assert_not_called()

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
