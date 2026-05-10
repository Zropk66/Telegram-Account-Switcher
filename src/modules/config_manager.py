# -*- coding: utf-8 -*-
"""
⚠️ 已弃用 (Deprecated)

此模块已弃用，请使用 src.modules.config.service.ConfigService 替代。
ConfigManage 类已被 ConfigService 取代，功能完全一致。

迁移指南:
    旧代码: from src.modules.config_manager import ConfigManage
            config = ConfigManage()

    新代码: from src.modules.config import ConfigService
            config = ConfigService()

此文件保留仅为兼容性，将在未来版本中删除。
"""
import warnings

warnings.warn(
    "config_manager 模块已弃用，请使用 src.modules.config.ConfigService 替代。"
    "此模块将在未来版本中删除。",
    DeprecationWarning,
    stacklevel=2
)

# 转发到新的实现
from src.modules.config.service import ConfigService

# 保持旧类名兼容
ConfigManage = ConfigService

__all__ = ['ConfigManage', 'ConfigService']
