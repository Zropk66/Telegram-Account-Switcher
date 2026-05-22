"""只读配置文件访问器。"""

import json
from pathlib import Path
from typing import Any

from .config import PathConfig


class ConfigLoadError(Exception):
    """配置文件加载异常。"""
    pass


class ConfigData:
    """配置文件数据接口。"""

    _CONFIG_FILENAME = PathConfig.CONFIG_FILE

    @staticmethod
    def path() -> Path:
        """获取配置文件路径。"""
        return Path.cwd() / ConfigData._CONFIG_FILENAME

    @staticmethod
    def read(key: str, default: Any = None) -> Any:
        """读取顶层配置项。"""
        try:
            config_file = ConfigData.path()
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get(key, default)
        except json.JSONDecodeError as e:
            raise ConfigLoadError(f"JSON 语法错误: {e}") from e
        except IOError as e:
            raise ConfigLoadError(f"文件读取失败: {e}") from e
        return default

    @staticmethod
    def section(name: str) -> dict:
        """读取特定的配置节（如 'tags'）。"""
        return ConfigData.read(name, {})

    @staticmethod
    def exists() -> bool:
        """configs.json 是否存在。"""
        return ConfigData.path().exists()

    @staticmethod
    def all() -> dict:
        """解析并返回完整的配置字典。"""
        try:
            config_file = ConfigData.path()
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigLoadError(f"JSON 语法错误: {e}") from e
        except IOError as e:
            raise ConfigLoadError(f"文件读取失败: {e}") from e
        return {}

    @staticmethod
    def as_provider():
        """转换为 ConfigProvider 接口对象。"""
        return _ConfigDataProvider()


class _ConfigDataProvider:
    """配置数据提供者。"""
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """获取配置值。"""
        return ConfigData.read(key, default)
