"""
TelegramEnvService 单元测试。
"""
import base64
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.env_service import TelegramEnvService
from src.core.exceptions import TASException


def test_extract_path():
    """验证路径提取逻辑。"""
    assert TelegramEnvService._extract_path('"C:\\Program Files\\Telegram\\Telegram.exe" --test') == "C:\\Program Files\\Telegram\\Telegram.exe"
    assert TelegramEnvService._extract_path('C:\\Telegram\\Telegram.exe') == "C:\\Telegram\\Telegram.exe"
    assert TelegramEnvService._extract_path('C:\\Telegram\\Telegram.exe --test') == "C:\\Telegram\\Telegram.exe"
    with pytest.raises(AttributeError):
        TelegramEnvService._extract_path('')


@patch("winreg.OpenKey")
@patch("winreg.QueryValue")
def test_search_client_success(mock_query, mock_open, tmp_path):
    """验证成功搜索客户端。"""
    exe_file = tmp_path / "Telegram.exe"
    exe_file.touch()

    mock_query.return_value = f'"{exe_file}" -- "%1"'

    client, parent = TelegramEnvService.search_client()
    assert client == "Telegram.exe"
    assert Path(parent) == tmp_path


@patch("winreg.OpenKey")
def test_search_client_failure(mock_open):
    """验证搜索客户端失败行为。"""
    mock_open.side_effect = FileNotFoundError()

    with pytest.raises(TASException, match="无法定位 Telegram 客户端"):
        TelegramEnvService.search_client()


def test_scan_accounts_not_dir():
    """验证路径非目录时返回空字典。"""
    assert TelegramEnvService.scan_accounts("non_existent_directory") == {}


def test_scan_accounts_success(tmp_path):
    """验证成功扫描账户。"""
    base_dir = tmp_path / "accounts"
    base_dir.mkdir()

    (base_dir / "random_dir").mkdir()
    (base_dir / "random_dir" / "random_file.txt").touch()

    tdata1 = base_dir / "tdata1"
    tdata1.mkdir()
    (tdata1 / "key_datas").write_bytes(b"dummy_key_data")
    (tdata1 / "tas_tag").write_text("tag_one", encoding="utf-8")

    tdata2 = base_dir / "tdata2"
    tdata2.mkdir()
    (tdata2 / "D877F783D5D3EF8Cs").write_bytes(b"dummy_identity")
    maps_dir = tdata2 / "D877F783D5D3EF8C"
    maps_dir.mkdir()
    (maps_dir / "maps").write_bytes(b"dummy_maps")

    with patch("src.core.crypto_service.AccountDataCryptoService.decrypt_account_id") as mock_decrypt:
        mock_decrypt.side_effect = lambda path, passcode: "user_123" if path.name == "tdata1" else "user_456"

        results = TelegramEnvService.scan_accounts(str(base_dir))

        assert len(results) == 2
        assert "tdata1" in results
        assert "tdata2" in results
        assert "random_dir" not in results

        acc1 = results["tdata1"]
        assert acc1["id"] == "user_123"
        assert acc1["tag"] == "tag_one"
        assert acc1["folder"] == "tdata1"
        assert base64.b64decode(acc1["key"]) == b"dummy_key_data"
        assert acc1["identity"] == ""
        assert acc1["info"] == ""

        acc2 = results["tdata2"]
        assert acc2["id"] == "user_456"
        assert acc2["tag"] == "tdata2"
        assert acc2["folder"] == "tdata2"
        assert base64.b64decode(acc2["identity"]) == b"dummy_identity"
        assert base64.b64decode(acc2["info"]) == b"dummy_maps"
        assert acc2["key"] == ""
