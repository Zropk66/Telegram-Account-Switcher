"""
ConfigStorage 配置存储单元测试。

验证配置文件加载、损坏回退、原子写入和字段过滤。
"""
import json
from unittest.mock import patch

import pytest

from src.core.config.storage import ConfigStorage


DEFAULT_CONFIG = {
    "client": "Telegram.exe",
    "path": "",
    "default": "",
    "tags": {},
    "log_output": True,
    "agreed_to_decrypt": False,
}


@pytest.fixture
def temp_config_path(tmp_path):
    """提供临时配置文件路径。"""
    return tmp_path / "config.json"


@pytest.fixture
def storage(temp_config_path):
    """提供 ConfigStorage 实例。"""
    return ConfigStorage(temp_config_path, DEFAULT_CONFIG)


def test_load_missing_file_creates_default(temp_config_path, storage):
    """验证首次运行时能自动创建默认配置文件。"""
    assert not temp_config_path.exists()

    config = storage.load()

    assert temp_config_path.exists()
    assert config == DEFAULT_CONFIG

    with open(temp_config_path, "r", encoding="utf-8") as f:
        saved_config = json.load(f)
    assert saved_config == DEFAULT_CONFIG


def test_load_corrupted_json_fallback(temp_config_path, storage):
    """验证配置文件损坏时回退到默认值，避免启动失败。"""
    with open(temp_config_path, "w", encoding="utf-8") as f:
        f.write("{this is not valid JSON}")

    config = storage.load()
    assert config == DEFAULT_CONFIG


def test_atomic_write_tmp_then_replace(temp_config_path, storage):
    """验证保存配置时使用临时文件加原子替换策略。"""
    test_config = {**DEFAULT_CONFIG, "client": "TelegramTest.exe"}

    with patch("os.replace") as mock_replace:
        storage.save(test_config)

        temp_file = temp_config_path.with_suffix(".tmp")
        mock_replace.assert_called_once_with(temp_file, temp_config_path)

    storage.save(test_config)
    with open(temp_config_path, "r", encoding="utf-8") as f:
        saved_config = json.load(f)
    assert saved_config["client"] == "TelegramTest.exe"


def test_save_filters_non_default_fields(temp_config_path, storage):
    """验证运行时字段不会泄露到持久化配置文件。"""
    config_with_extra = {
        **DEFAULT_CONFIG,
        "client": "Test.exe",
        "runtime_field_1": "should_not_save",
        "runtime_field_2": {"nested": "data"},
        "tag": "temp_tag",
        "pwd": "secret",
    }

    storage.save(config_with_extra)

    with open(temp_config_path, "r", encoding="utf-8") as f:
        saved_config = json.load(f)

    assert set(saved_config.keys()) == set(DEFAULT_CONFIG.keys())
    assert "runtime_field_1" not in saved_config
    assert "runtime_field_2" not in saved_config
    assert "tag" not in saved_config
    assert "pwd" not in saved_config
    assert saved_config["client"] == "Test.exe"
