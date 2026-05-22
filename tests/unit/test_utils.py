"""核心工具单元测试。"""

import pytest

from src.core.utils import safe_rename, search_file_in_dirs


def test_safe_rename_success(tmp_path):
    """验证安全重命名成功后，源路径被替换为目标路径。"""
    src = tmp_path / "source.txt"
    dst = tmp_path / "destination.txt"

    src.write_text("test content", encoding="utf-8")

    with safe_rename(src, dst):
        pass

    assert not src.exists()
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "test content"


def test_safe_rename_rollback_on_exception(tmp_path):
    """验证上下文中断时会尽量恢复原始文件位置。"""
    src = tmp_path / "source.txt"
    dst = tmp_path / "destination.txt"

    src.write_text("test content", encoding="utf-8")

    class TestException(Exception):
        """测试异常类。"""
        pass

    with pytest.raises(TestException):
        with safe_rename(src, dst):
            raise TestException("intentional failure")

    assert src.exists()
    assert not dst.exists()
    assert src.read_text(encoding="utf-8") == "test content"


def test_safe_rename_src_not_exists(tmp_path):
    """验证源路径不存在时保持幂等，适配首次启动或空目录场景。"""
    src = tmp_path / "not_exists.txt"
    dst = tmp_path / "destination.txt"

    with safe_rename(src, dst):
        pass

    assert not src.exists()
    assert not dst.exists()


def test_search_file_in_dirs_finds_tag(tmp_path):
    """验证可通过 tas_tag 内容定位对应账户文件夹。"""
    base_dir = tmp_path / "telegram"
    base_dir.mkdir()

    account1 = base_dir / "tdata-account1"
    account1.mkdir()
    (account1 / "tas_tag").write_text("my_tag", encoding="utf-8")

    account2 = base_dir / "tdata-account2"
    account2.mkdir()
    (account2 / "tas_tag").write_text("other_tag", encoding="utf-8")

    result = search_file_in_dirs(base_dir, "my_tag")
    assert result == "tdata-account1"


def test_search_file_in_dirs_not_found(tmp_path):
    """验证未匹配到账户标签时返回 None。"""
    base_dir = tmp_path / "telegram"
    base_dir.mkdir()

    account1 = base_dir / "tdata-account1"
    account1.mkdir()
    (account1 / "tas_tag").write_text("my_tag", encoding="utf-8")

    result = search_file_in_dirs(base_dir, "not_existing_tag")
    assert result is None


def test_search_file_in_dirs_base_not_a_directory(tmp_path):
    """验证基础路径不是目录时不会继续扫描。"""
    not_dir = tmp_path / "not_a_dir.txt"
    not_dir.write_text("content", encoding="utf-8")

    result = search_file_in_dirs(not_dir, "my_tag")
    assert result is None


def test_search_file_in_dirs_tas_tag_corrupted(tmp_path):
    """验证损坏的 tas_tag 文件不会中断目录搜索。"""
    base_dir = tmp_path / "telegram"
    base_dir.mkdir()

    account1 = base_dir / "tdata-account1"
    account1.mkdir()
    (account1 / "tas_tag").write_bytes(b"\xff\xfe\xfd")

    result = search_file_in_dirs(base_dir, "my_tag")
    assert result is None


def test_search_file_in_dirs_no_tas_tag(tmp_path):
    """验证缺少 tas_tag 的文件夹会被跳过。"""
    base_dir = tmp_path / "telegram"
    base_dir.mkdir()

    account1 = base_dir / "tdata-account1"
    account1.mkdir()

    result = search_file_in_dirs(base_dir, "my_tag")
    assert result is None
