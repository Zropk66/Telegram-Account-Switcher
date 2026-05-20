"""
配置描述符定义。

通过 Python 的描述符协议实现透明的配置读写
"""
import weakref
from typing import Any, Optional, Type, TYPE_CHECKING, TypeVar, Generic

if TYPE_CHECKING:
    from src.core.config.service import ConfigService

T = TypeVar('T')


class ConfigField(Generic[T]):
    """配置属性描述符。"""

    __slots__ = ("name", "expected_type", "default_value", "_cache")

    def __init__(self, name: str, expected_type: Type[T], default_value: Optional[T] = None):
        """初始化。"""
        self.name = name
        self.expected_type = expected_type
        self.default_value = default_value
        self._cache = weakref.WeakKeyDictionary()

    def __get__(self, instance: Optional["ConfigService"], owner: Type["ConfigService"]) -> Optional[T]:
        """获取字段值。"""
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
        """更新字段值并持久化。"""
        if value is not None and not isinstance(value, self.expected_type):
            raise TypeError(
                f"字段 '{self.name}' 类型错误：期望 {self.expected_type.__name__}, 实际为 {type(value).__name__}"
            )

        self._cache[instance] = value

        # noinspection PyProtectedMember
        with instance._lock:
            config = getattr(instance, "_config")
            config[self.name] = value

            # noinspection PyProtectedMember
            instance._storage._config_changed = True
            # noinspection PyProtectedMember
            if not instance._storage._batch:
                # noinspection PyProtectedMember
                instance._storage.save(config)

    def clear_cache(self, instance: Any) -> None:
        """强制清理缓存，使下次读取直接命中内部字典。"""
        if instance in self._cache:
            del self._cache[instance]
