"""
配置服务门面。

本模块是系统的配置中心，协调 ConfigStorage (磁盘)、RuntimeState (内存)
以及各功能模块的配置需求。它采用单例模式，对外提供统一的配置操作 API。
"""

import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Dict, Any, Optional, Callable

from src.core.config.data import ConfigData
from src.core.config.fields import ConfigField
from src.core.config.key_manager import TelegramKeyManager
from src.core.config.runtime import RuntimeState
from src.core.config.storage import ConfigStorage
from src.core.utils import format_timedelta, search_file_in_dirs


class ConfigService:
    """
    配置服务单例门面。
    """

    # 持久化配置字段（由描述符实现自动处理）
    client: str = ConfigField("client", str, "Telegram.exe")
    path: str = ConfigField("path", str, "")
    default: str = ConfigField("default", str, "")
    tags: Dict[str, Dict[str, Any]] = ConfigField("tags", dict, {})
    log_output: bool = ConfigField("log_output", bool, True)
    agreed_to_decrypt: bool = ConfigField("agreed_to_decrypt", bool, False)

    # 基础默认值，作为 JSON 读取失败时的兜底
    _DEFAULT_CONFIG = {
        "client": "Telegram.exe",
        "path": "",
        "default": "",
        "tags": {},
        "log_output": True,
        "agreed_to_decrypt": False,
    }

    _instance = None
    _lock = RLock()

    def __new__(cls):
        """内部方法：__new__。"""
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
                cls._instance.__initialized = False
        return cls._instance

    def __init__(self, _storage: Optional["ConfigStorage"] = None):
        """初始化。"""
        with self._lock:
            if self.__initialized:
                return

            self._runtime = RuntimeState()
            self._storage = _storage or ConfigStorage(
                config_path=ConfigData.path(),
                default_config=self._DEFAULT_CONFIG,
                error_handler=self._error_handler
            )

            self._config = self._storage.load()
            self.__initialized = True

            from src.core.config.storage import InMemoryConfigStorage
            if not isinstance(self._storage, InMemoryConfigStorage):
                self._storage.start_auto_save(self)

    _log_handler: Optional[Callable[[str], None]] = None

    @classmethod
    def get_instance(cls) -> "ConfigService":
        """get_instance 方法。"""
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """释放配置单例，供测试隔离使用。"""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown()
            cls._instance = None
            cls._log_handler = None

    @classmethod
    def set_log_handler(cls, handler: Optional[Callable[[str], None]]) -> None:
        """注入外部日志处理逻辑。"""
        cls._log_handler = handler

    def _error_handler(self, message: str) -> None:
        """存储层错误转译。"""
        if self._log_handler:
            try:
                self._log_handler(message)
            except (RuntimeError, TypeError):
                pass

    def shutdown(self) -> None:
        """停机清理：停止自动保存，执行最终落盘。"""
        self._storage.stop_auto_save()
        # noinspection PyProtectedMember
        if self._storage._config_changed:
            self._storage.save(self._config)

    def __enter__(self):
        """进入批量更新模式（在此期间不进行磁盘同步）。"""
        # noinspection PyProtectedMember
        self._storage._batch = True
        self._snapshot = deepcopy(self._config)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出批量更新模式：成功则落盘，异常则回滚。"""
        # noinspection PyProtectedMember
        self._storage._batch = False
        if exc_type is not None:
            self._config = self._snapshot
            # noinspection PyProtectedMember
            self._storage._config_changed = True
            # 回滚后必须强制清除描述符缓存，否则读取到的仍是脏数据
            from src.core.config.fields import ConfigField
            for _, field in self.__class__.__dict__.items():
                if isinstance(field, ConfigField):
                    field.clear_cache(self)
        else:
            # noinspection PyProtectedMember
            if self._storage._config_changed:
                self._storage.save(self._config)

    @property
    def start_time(self) -> Optional[datetime]:
        """start_time 方法。"""
        with self._lock: return self._runtime.start_time

    @start_time.setter
    def start_time(self, v):
        """start_time 方法。"""
        with self._lock: self._runtime.start_time = v

    @property
    def tag(self) -> str:
        """tag 方法。"""
        with self._lock: return self._runtime.tag

    @tag.setter
    def tag(self, v):
        """tag 方法。"""
        with self._lock: self._runtime.tag = str(v) if v is not None else ""

    @property
    def force_key_login(self) -> bool:
        """force_key_login 方法。"""
        with self._lock: return self._runtime.force_key_login

    @force_key_login.setter
    def force_key_login(self, v):
        """force_key_login 方法。"""
        with self._lock: self._runtime.force_key_login = bool(v)

    @property
    def pwd(self) -> str:
        """pwd 方法。"""
        with self._lock: return self._runtime.password

    @pwd.setter
    def pwd(self, v):
        """pwd 方法。"""
        with self._lock: self._runtime.password = str(v) if v is not None else ""

    @property
    def decrypted(self) -> bool:
        """decrypted 方法。"""
        with self._lock: return self._runtime.decrypted

    @decrypted.setter
    def decrypted(self, v):
        """decrypted 方法。"""
        with self._lock: self._runtime.decrypted = bool(v)

    @property
    def has_backup(self) -> bool:
        """has_backup 方法。"""
        return self.has_complete_keys(self.tag)

    @property
    def configs(self) -> Dict[str, Any]:
        """获取当前配置数据的浅拷贝。"""
        return self._config.copy()

    @property
    def config_file(self) -> Path:
        """config_file 方法。"""
        # noinspection PyProtectedMember
        return self._storage._config_path

    def get_all_accounts(self) -> Dict[str, Dict[str, Any]]:
        """get_all_accounts 方法。"""
        return dict(self.tags)

    def get_tag_list(self) -> list[str]:
        """get_tag_list 方法。"""
        return list(self.tags.keys())

    def get_account(self, tag: str) -> Dict[str, Any]:
        """获取特定账户配置，不存在时返回空模板。"""
        return self.tags.get(tag, {'id': '', 'folder': '', 'info': '', 'identity': '', 'key': ''})

    def set_account(self, tag: str, data: Dict[str, Any]) -> None:
        """更新/新增账户配置。"""
        with self._lock:
            tags: Dict[str, Dict[str, Any]] = dict(self.tags)
            tags[tag] = data
            self.tags = tags

    def remove_account(self, tag: str) -> None:
        """remove_account 方法。"""
        tags: Dict[str, Dict[str, Any]] = self.tags.copy()
        if tag in tags:
            del tags[tag]
            self.tags = tags

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """在一次事务中应用多项配置更新。"""
        with self:
            for key, value in updates.items():
                setattr(self, key, value)

    def login_with_keys(self, tag: str, tdata_path: str) -> bool:
        """login_with_keys 方法。"""
        return TelegramKeyManager.login_with_keys(tag, tdata_path, self)

    def backup_account_keys(self, tag: str, folder_path: Path) -> bool:
        """backup_account_keys 方法。"""
        return TelegramKeyManager.backup_keys(tag, folder_path, self)

    def has_complete_keys(self, tag: str) -> bool:
        """has_complete_keys 方法。"""
        acc = self.get_account(tag)
        return all(acc.get(k) for k in ('key', 'identity', 'info'))

    def sync_all_account_paths(self) -> None:
        """扫描磁盘目录，将账户文件夹信息与配置表进行同步。"""
        if not self.path or not os.path.isdir(self.path):
            return

        updated_tags: Dict[str, Dict[str, Any]] = self.tags.copy()
        changed = False
        for tag, info in updated_tags.items():
            real_folder = search_file_in_dirs(self.path, tag)
            if real_folder and info.get("folder") != real_folder:
                info["folder"] = real_folder
                changed = True
        if changed:
            self.tags = updated_tags

    def watch_time(self) -> str:
        """格式化程序运行时间。"""
        start_time = self.start_time
        if start_time is None:
            return "0时0分0秒"
        return format_timedelta(datetime.now() - start_time)
