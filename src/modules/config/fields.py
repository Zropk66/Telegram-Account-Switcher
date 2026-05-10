# -*- coding: utf-8 -*-
# @File    : runtime.py
# @Time    : 2026/5/10 16:28
# @Author  : Zropk
"""配置字段描述符 - 对应原 ConfigField"""
import weakref
from typing import Any, Optional, Type


class ConfigField:
    """配置字段描述符"""

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

        if value is None:
            value = self.default_value

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

        with instance._lock:
            config = getattr(instance, "_config")
            config[self.name] = value

            instance._storage._config_changed = True
            if not instance._storage._batch:
                instance._storage.save(config)

    def clear_cache(self, instance: Any) -> None:
        if instance in self._cache:
            del self._cache[instance]
