"""
轻量配置读取层

不依赖 ConfigService，直接读 configs.json。
主要给 Logger 等需要在 ConfigService 初始化之前就拿到配置的模块用。
"""
import json
from pathlib import Path
from typing import Any


class ConfigData:
    """静态工具类，所有方法都是 classmethod / staticmethod，不需要实例化"""

    _CONFIG_FILENAME = "configs.json"

    @staticmethod
    def path() -> Path:
        """返回 configs.json 的路径"""
        return Path.cwd() / ConfigData._CONFIG_FILENAME

    @staticmethod
    def read(key: str, default: Any = None) -> Any:
        """读取指定配置项，找不到时返回 default。"""
        try:
            config_file = ConfigData.path()
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get(key, default)
        except (json.JSONDecodeError, IOError, Exception):
            pass
        return default

    @staticmethod
    def section(name: str) -> dict:
        """读取配置中的某个顶层 section（如 "tags"），不存在则返回空字典。"""
        try:
            config_file = ConfigData.path()
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get(name, {})
        except (json.JSONDecodeError, IOError, Exception):
            pass
        return {}

    @staticmethod
    def exists() -> bool:
        """配置文件是否存在"""
        return ConfigData.path().exists()

    @staticmethod
    def all() -> dict:
        """返回完整配置字典，读失败给空字典"""
        try:
            config_file = ConfigData.path()
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError, Exception):
            pass
        return {}

    @staticmethod
    def as_provider():
        """返回一个只暴露 get(key, default) 接口的对象，方便依赖注入"""
        return _ConfigDataProvider()


class _ConfigDataProvider:
    """把 ConfigData 包一层，对外只提供 get 方法"""

    def get(self, key: str, default: Any = None) -> Any:
        return ConfigData.read(key, default)
