# -*- coding: utf-8 -*-
# @File    : runtime.py
# @Time    : 2026/5/10 17:03
# @Author  : Zropk
"""
配置数据访问 - 独立模块，避免循环导入

此模块提供独立的配置数据访问功能，不依赖 ConfigService 类，
供 Logger 等需要在 ConfigService 初始化前访问配置的模块使用。
"""
import json
from pathlib import Path
from typing import Any


class ConfigData:
    """
    配置数据访问类 - 提供独立的配置数据访问功能

    此类不依赖 ConfigService，直接访问配置文件，
    用于避免循环导入问题。

    所有方法均为静态方法，无需实例化即可使用。

    Example:
        # >>> from src.modules.config.data import ConfigData
        # >>> log_output = ConfigData.read("log_output", False)
        # >>> client = ConfigData.read("client", "Telegram.exe")
        # >>> config_path = ConfigData.path()
        # >>> all_config = ConfigData.all()
    """

    _CONFIG_FILENAME = "configs.json"

    @staticmethod
    def path() -> Path:
        """获取配置文件路径"""
        return Path.cwd() / ConfigData._CONFIG_FILENAME

    @staticmethod
    def read(key: str, default: Any = None) -> Any:
        """
        读取配置项的值

        Args:
            key: 配置项键名
            default: 默认值，当配置不存在或读取失败时返回

        Returns:
            配置项的值，或默认值
        """
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
        """
        读取配置中的某个 section

        Args:
            name: 配置节名称（如 "tags"）

        Returns:
            该 section 的字典，如果不存在返回空字典
        """
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
        """检查配置文件是否存在"""
        return ConfigData.path().exists()

    @staticmethod
    def all() -> dict:
        """
        获取完整配置字典

        Returns:
            完整配置字典，如果读取失败返回空字典
        """
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
        """
        返回一个配置提供者对象，用于依赖注入

        Returns:
            实现了 get(key, default) 方法的对象
        """
        return _ConfigDataProvider()


class _ConfigDataProvider:
    """内部类：将 ConfigData 包装为提供者接口"""

    def get(self, key: str, default: Any = None) -> Any:
        return ConfigData.read(key, default)
