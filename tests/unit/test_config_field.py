"""
ConfigField 描述符单元测试。

验证配置字段描述符的缓存、类型保护、自动持久化和批量更新行为。
"""
import pytest
from threading import RLock
from unittest.mock import MagicMock

from src.core.config.fields import ConfigField


class MockConfigService:
    """为 ConfigField 提供最小化的配置服务替身。"""

    def __init__(self):
        self._lock = RLock()
        self._config = {}
        self._storage = MagicMock()
        self._storage._config_changed = False
        self._storage._batch = False
        self._storage.save = MagicMock()

    test_str = ConfigField("test_str", str, "default_str")
    test_int = ConfigField("test_int", int, 42)
    test_bool = ConfigField("test_bool", bool, True)
    test_dict = ConfigField("test_dict", dict, {})


class TestConfigField:
    """验证配置描述符的读写语义与一致性约束。"""

    def test_field_get_returns_cached_value(self):
        """验证读取时优先返回缓存，避免重复解析配置数据。"""
        config = MockConfigService()

        config._config["test_str"] = "initial_value"

        first_read = config.test_str
        assert first_read == "initial_value"

        # 直接修改底层字典，用于确认描述符缓存不会被绕过写入影响
        config._config["test_str"] = "modified_in_config"

        second_read = config.test_str
        assert second_read == "initial_value"

    def test_field_set_type_check(self):
        """验证字段赋值必须符合声明类型，防止配置数据被污染。"""
        config = MockConfigService()

        config.test_str = "valid_string"
        assert config.test_str == "valid_string"

        config.test_int = 100
        assert config.test_int == 100

        config.test_bool = False
        assert config.test_bool is False

        config.test_dict = {"key": "value"}
        assert config.test_dict == {"key": "value"}

        with pytest.raises(TypeError) as excinfo:
            config.test_str = 123
        assert "test_str" in str(excinfo.value)
        assert "str" in str(excinfo.value)
        assert "int" in str(excinfo.value)

        with pytest.raises(TypeError) as excinfo:
            config.test_int = "not_an_int"
        assert "test_int" in str(excinfo.value)
        assert "int" in str(excinfo.value)
        assert "str" in str(excinfo.value)

        with pytest.raises(TypeError) as excinfo:
            config.test_bool = "not_a_bool"
        assert "test_bool" in str(excinfo.value)
        assert "bool" in str(excinfo.value)
        assert "str" in str(excinfo.value)

        with pytest.raises(TypeError) as excinfo:
            config.test_dict = "not_a_dict"
        assert "test_dict" in str(excinfo.value)
        assert "dict" in str(excinfo.value)
        assert "str" in str(excinfo.value)

    def test_field_set_triggers_persistence(self):
        """验证普通写入会立即通知存储层，避免配置修改丢失。"""
        config = MockConfigService()

        config._storage._batch = False
        config.test_str = "new_value"

        config._storage.save.assert_called_once()
        assert config._storage._config_changed is True
        assert config._config["test_str"] == "new_value"

    def test_field_set_batch_mode_skips_save(self):
        """验证批量模式只标记脏数据，不在每次字段写入时落盘。"""
        config = MockConfigService()

        config._storage._batch = True
        config._storage.save.reset_mock()

        config.test_str = "batch_value_1"
        config.test_int = 999
        config.test_bool = False

        assert config._storage.save.call_count == 0
        assert config._storage._config_changed is True
        assert config._config["test_str"] == "batch_value_1"
        assert config._config["test_int"] == 999
        assert config._config["test_bool"] is False

    def test_field_clear_cache(self):
        """验证清除缓存后，下次读取会重新解析底层配置值。"""
        config = MockConfigService()

        config._config["test_str"] = "cached_value"
        assert config.test_str == "cached_value"

        config._config["test_str"] = "updated_config_value"
        assert config.test_str == "cached_value"

        MockConfigService.test_str.clear_cache(config)

        assert config.test_str == "updated_config_value"

    def test_field_get_with_none_value_uses_default(self):
        """验证配置值为 None 时回退到字段默认值。"""
        config = MockConfigService()
        config._config["test_str"] = None

        assert config.test_str == "default_str"

    def test_field_get_with_type_conversion(self):
        """验证读取旧配置时允许可恢复的类型转换。"""
        config = MockConfigService()

        MockConfigService.test_int.clear_cache(config)
        config._config["test_int"] = "123"
        assert config.test_int == 123

        MockConfigService.test_str.clear_cache(config)
        config._config["test_str"] = 456
        assert config.test_str == "456"

        MockConfigService.test_int.clear_cache(config)
        config._config["test_int"] = "not_a_number"
        assert config.test_int == 42
