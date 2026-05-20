"""
轻量配置访问层。

该模块不依赖 ConfigService，直接通过 JSON 读取 configs.json。
主要用于 Logger 等需要在核心服务初始化之前就读取环境配置（如日志是否输出到文件）的模块。
"""

import json
from pathlib import Path
from typing import Any

from .config import PathConfig


class ConfigLoadError(Exception):
    """当配置文件格式损坏或读取权限受限时抛出。"""
    pass


class ConfigData:
    """静态工具类：直接访问物理配置文件。"""

    _CONFIG_FILENAME = PathConfig.CONFIG_FILE

    @staticmethod
    def path() -> Path:
        """配置文件在当前工作目录下的位置。"""
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
    """内部包装类，适配 Logger 模块的 ConfigProvider 契约。"""
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """get 方法。"""
        return ConfigData.read(key, default)
