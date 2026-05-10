"""
配置字段描述符

用 Python descriptor 协议实现带类型检查和缓存的自定义属性。
赋值时自动触发持久化，读取时走缓存避免重复解析。
"""
import weakref
from typing import Any, Optional, Type


class ConfigField:
    """描述符：在 ConfigService 上定义一个带类型约束的配置字段"""

    __slots__ = ("name", "expected_type", "default_value", "_cache")

    def __init__(self, name: str, expected_type: type, default_value: Any = None):
        self.name = name
        self.expected_type = expected_type
        self.default_value = default_value
        self._cache = weakref.WeakKeyDictionary()

    def __get__(self, instance: Optional["ConfigService"], owner: Type["ConfigService"]) -> Any:
        if instance is None:
            return self

        if instance in self._cache:
            return self._cache[instance]

        config = getattr(instance, "_config", {})
        value = config.get(self.name)

        # 没有就用默认值
        if value is None:
            value = self.default_value

        # 类型不对就尝试强转，转不了还是用默认值
        if value is not None and not isinstance(value, self.expected_type):
            try:
                value = self.expected_type(value)
            except (ValueError, TypeError):
                value = self.default_value

        self._cache[instance] = value
        return value

    def __set__(self, instance: "ConfigService", value: Any) -> None:
        if value is not None and not isinstance(value, self.expected_type):
            raise TypeError(
                f"{self.name} expected {self.expected_type.__name__}, got {type(value).__name__}"
            )

        self._cache[instance] = value

        # 写入配置字典并触发持久化
        with instance._lock:
            config = getattr(instance, "_config")
            config[self.name] = value

            instance._storage._config_changed = True
            if not instance._storage._batch:
                instance._storage.save(config)

    def clear_cache(self, instance: Any) -> None:
        """清除指定实例的缓存，下次读取会重新从 _config 取值"""
        if instance in self._cache:
            del self._cache[instance]
