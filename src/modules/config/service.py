# -*- coding: utf-8 -*-
# @File    : runtime.py
# @Time    : 2026/5/10 16:28
# @Author  : Zropk
"""配置服务 - 对应原 ConfigManage，完整还原所有方法"""
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Dict, Any, Optional, Callable

from src.modules.env_service import TelegramEnvService
from src.modules.config.runtime import RuntimeState
from src.modules.config.storage import ConfigStorage
from src.modules.config.key_manager import TelegramKeyManager
from src.modules.config.fields import ConfigField
from src.modules.config.data import ConfigData
from src.modules.utils import format_timedelta, search_file_in_dirs


class ConfigService:
    """配置管理类 (Facade/Coordinator) - 完整还原 ConfigManage 的所有方法"""

    # 配置字段描述符 - 持久化配置
    client: str = ConfigField("client", str, "Telegram.exe")
    path: str = ConfigField("path", str, "")
    default: str = ConfigField("default", str, "")
    tags: Dict[str, Dict[str, Any]] = ConfigField("tags", dict, {})
    log_output: bool = ConfigField("log_output", bool, True)
    agreed_to_decrypt: bool = ConfigField("agreed_to_decrypt", bool, False)

    _instance = None
    _lock = RLock()
    _DEFAULT_CONFIG = {
        "client": "Telegram.exe",
        "path": "",
        "default": "",
        "tags": {},
        "log_output": True,
        "agreed_to_decrypt": False,
    }

    def __new__(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
                cls._instance.__initialized = False
        return cls._instance

    def __init__(self):
        if self.__initialized:
            return

        self._runtime = RuntimeState()
        # 使用 ConfigData 获取配置路径，避免硬编码
        self._storage = ConfigStorage(
            config_path=ConfigData.path(),
            default_config=self._DEFAULT_CONFIG,
            error_handler=self._error_handler
        )
        self._config = self._storage.load()

        self.__initialized = True
        self._storage.start_auto_save(self)

    def _error_handler(self, message: str) -> None:
        """错误处理回调，使用依赖注入的日志记录器"""
        if self._log_handler:
            try:
                self._log_handler(message)
            except Exception:
                pass  # 如果日志处理器失败，静默处理

    # 类级别的日志处理器，可通过依赖注入设置
    _log_handler: Optional[Callable[[str], None]] = None

    @classmethod
    def set_log_handler(cls, handler: Optional[Callable[[str], None]]) -> None:
        """
        设置日志处理器（依赖注入入口）

        Args:
            handler: 日志处理函数，签名 (message: str) -> None
                    传入 None 可移除当前处理器
        """
        cls._log_handler = handler

    # ========== 生命周期方法 ==========

    def shutdown(self) -> None:
        """停止自动保存并落盘"""
        self._storage.stop_auto_save()
        if self._storage._config_changed:
            self._storage.save(self._config)

    def __del__(self):
        self._storage.stop_auto_save()

    def __enter__(self):
        """开启批量更新"""
        self._storage._batch = True
        self._snapshot = deepcopy(self._config)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """退出批量更新并保存"""
        self._storage._batch = False
        if exc_type is not None:
            self._config = self._snapshot
            self._storage._config_changed = True
        else:
            if self._storage._config_changed:
                self._storage.save(self._config)

    # ========== 运行时属性（线程安全） ==========

    @property
    def start_time(self) -> Optional[datetime]:
        with self._lock:
            return self._runtime.start_time

    @start_time.setter
    def start_time(self, value: Optional[datetime]) -> None:
        with self._lock:
            self._runtime.start_time = value

    @property
    def tag(self) -> str:
        with self._lock:
            return self._runtime.tag

    @tag.setter
    def tag(self, value: str) -> None:
        with self._lock:
            self._runtime.tag = str(value) if value is not None else ""

    @property
    def force_key_login(self) -> bool:
        with self._lock:
            return self._runtime.force_key_login

    @force_key_login.setter
    def force_key_login(self, value: bool) -> None:
        with self._lock:
            self._runtime.force_key_login = bool(value)

    @property
    def process_status(self) -> bool:
        with self._lock:
            return self._runtime.process_status

    @process_status.setter
    def process_status(self, value: bool) -> None:
        with self._lock:
            self._runtime.process_status = bool(value)

    @property
    def complete(self) -> bool:
        with self._lock:
            return self._runtime.complete

    @complete.setter
    def complete(self, value: bool) -> None:
        with self._lock:
            self._runtime.complete = bool(value)

    @property
    def pwd(self) -> str:
        """密码属性（运行时）"""
        with self._lock:
            return self._runtime.password

    @pwd.setter
    def pwd(self, value: str) -> None:
        with self._lock:
            self._runtime.password = str(value) if value is not None else ""

    @property
    def decrypted(self) -> bool:
        with self._lock:
            return self._runtime.decrypted

    @decrypted.setter
    def decrypted(self, value: bool) -> None:
        with self._lock:
            self._runtime.decrypted = bool(value)

    @property
    def has_backup(self) -> bool:
        """检查当前标签是否有备份密钥"""
        return self.has_complete_keys(self.tag)

    # ========== 配置访问方法 ==========

    @property
    def configs(self) -> Dict[str, Any]:
        """获取配置副本"""
        return self._config.copy()

    @property
    def config_file(self) -> Path:
        """获取配置文件路径"""
        return self._storage._config_path

    @property
    def default_configs(self) -> Dict[str, Any]:
        """获取默认配置"""
        return self._DEFAULT_CONFIG.copy()

    def clear_cache(self) -> None:
        """清除字段缓存"""
        cls = type(self)
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, ConfigField):
                attr.clear_cache(self)

    # ========== 账户管理方法 ==========

    def get_all_accounts(self) -> Dict[str, Dict[str, Any]]:
        """获取所有账户"""
        return dict(self.tags)

    def get_account(self, tag: str) -> Dict[str, Any]:
        """获取单个账户"""
        tags: Dict[str, Dict[str, Any]] = self.tags
        return tags.get(tag, {'id': '', 'folder': '', 'info': '', 'identity': '', 'key': ''})

    def set_account(self, tag: str, account_data: Dict[str, Any]) -> None:
        """设置账户数据"""
        with self._lock:
            tags = dict(self.tags)
            tags[tag] = account_data
            self.tags = tags

    def remove_account(self, tag: str) -> None:
        """移除账户"""
        tags = dict(self.tags)
        if tag in tags:
            del tags[tag]
            self.tags = tags

    def get_tag_list(self) -> list:
        """获取标签列表"""
        return list(self.tags.keys())

    # ========== 密钥管理方法 ==========

    def login_with_keys(self, tag: str, tdata_path: str) -> bool:
        """使用密钥登录"""
        return TelegramKeyManager.login_with_keys(tag, tdata_path, self)

    def backup_account_keys(self, tag: str, folder_path: Path) -> bool:
        """备份账户密钥"""
        return TelegramKeyManager.backup_keys(tag, folder_path, self)

    def has_complete_keys(self, tag: str) -> bool:
        """检查账户是否有完整密钥"""
        account = self.get_account(tag)
        return bool(account.get('key') and account.get('identity') and account.get('info'))

    # ========== 环境扫描方法 ==========

    @staticmethod
    def scan_accounts_from_path(base_path: str, passcode: str = None) -> Dict[str, Dict[str, Any]]:
        """从路径扫描账户"""
        return TelegramEnvService.scan_accounts(base_path, passcode)

    def sync_all_account_paths(self) -> None:
        """同步所有账户路径"""
        if not self.path or not os.path.isdir(self.path):
            return

        updated_tags = self.tags.copy()
        changed = False
        for tag, info in updated_tags.items():
            real_folder = search_file_in_dirs(self.path, tag)
            if real_folder and info.get("folder") != real_folder:
                info["folder"] = real_folder
                changed = True
        if changed:
            self.tags = updated_tags

    # ========== 批量操作方法 ==========

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """批量更新配置项"""
        with self:
            for field, value in updates.items():
                if hasattr(self, field):
                    setattr(self, field, value)

    # ========== 工具方法 ==========

    def watch_time(self) -> str:
        """获取运行时长"""
        start = self.start_time
        if start is None:
            return "0时0分0秒"
        return format_timedelta(datetime.now() - start)
