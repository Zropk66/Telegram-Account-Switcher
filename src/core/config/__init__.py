"""
配置管理公共入口。

导出配置服务、只读配置数据、路径常量和存储实现。
"""

from src.core.config.config import PathConfig
from src.core.config.data import ConfigData
from src.core.config.service import ConfigService
from src.core.config.storage import ConfigStorage, InMemoryConfigStorage

__all__ = [
    "ConfigService",
    "ConfigData",
    "PathConfig",
    "ConfigStorage",
    "InMemoryConfigStorage",
]
