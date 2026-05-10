"""
配置服务主入口

对外暴露所有配置相关的操作：读写持久化字段、管理账户列表、
密钥备份/恢复、环境扫描等。内部把存储、运行时状态、密钥管理
等职责委托给对应模块，本类只做协调。
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
from src.core.env_service import TelegramEnvService
from src.core.utils import format_timedelta, search_file_in_dirs


class ConfigService:
    """配置管理门面类，单例模式"""

    # -- 持久化配置字段 --
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
        self._storage = ConfigStorage(
            config_path=ConfigData.path(),
            default_config=self._DEFAULT_CONFIG,
            error_handler=self._error_handler
        )
        self._config = self._storage.load()

        self.__initialized = True
        self._storage.start_auto_save(self)

    def _error_handler(self, message: str) -> None:
        """存储层回调上来的错误，转发给日志处理器"""
        if self._log_handler:
            try:
                self._log_handler(message)
            except Exception:
                pass

    # 日志处理器，由外部注入
    _log_handler: Optional[Callable[[str], None]] = None

    @classmethod
    def set_log_handler(cls, handler: Optional[Callable[[str], None]]) -> None:
        """注入日志处理器，传 None 则清除。"""
        cls._log_handler = handler

    # -- 生命周期 --

    def shutdown(self) -> None:
        """停止后台保存线程，把脏数据落盘"""
        self._storage.stop_auto_save()
        if self._storage._config_changed:
            self._storage.save(self._config)

    def __del__(self):
        self._storage.stop_auto_save()

    def __enter__(self):
        """进入批量更新模式，期间不会触发自动保存"""
        self._storage._batch = True
        self._snapshot = deepcopy(self._config)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """退出批量更新：正常退出则保存，异常退出则回滚"""
        self._storage._batch = False
        if exc_type is not None:
            self._config = self._snapshot
            self._storage._config_changed = True
        else:
            if self._storage._config_changed:
                self._storage.save(self._config)

    # -- 运行时属性（线程安全） --

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
    def pwd(self) -> str:
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
        """当前 tag 对应的账户是否有完整密钥备份"""
        return self.has_complete_keys(self.tag)

    # -- 配置访问 --

    @property
    def configs(self) -> Dict[str, Any]:
        """返回配置的浅拷贝，防止外部直接修改内部字典"""
        return self._config.copy()

    @property
    def config_file(self) -> Path:
        return self._storage._config_path

    @property
    def default_configs(self) -> Dict[str, Any]:
        return self._DEFAULT_CONFIG.copy()

    def clear_cache(self) -> None:
        """清除所有 ConfigField 的实例缓存，下次读取会重新解析"""
        cls = type(self)
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, ConfigField):
                attr.clear_cache(self)

    # -- 账户管理 --

    def get_all_accounts(self) -> Dict[str, Dict[str, Any]]:
        """返回所有账户数据的副本"""
        return dict(self.tags)

    def get_account(self, tag: str) -> Dict[str, Any]:
        """获取指定账户，不存在则返回空壳字典"""
        tags: Dict[str, Dict[str, Any]] = self.tags
        return tags.get(tag, {'id': '', 'folder': '', 'info': '', 'identity': '', 'key': ''})

    def set_account(self, tag: str, account_data: Dict[str, Any]) -> None:
        """新增或覆盖某个账户的数据"""
        with self._lock:
            tags = dict(self.tags)
            tags[tag] = account_data
            self.tags = tags

    def remove_account(self, tag: str) -> None:
        """删除指定账户"""
        tags = dict(self.tags)
        if tag in tags:
            del tags[tag]
            self.tags = tags

    def get_tag_list(self) -> list:
        """返回所有账户标签"""
        return list(self.tags.keys())

    # -- 密钥操作 --

    def login_with_keys(self, tag: str, tdata_path: str) -> bool:
        """用配置中存储的密钥写回 tdata 目录，免密登录"""
        return TelegramKeyManager.login_with_keys(tag, tdata_path, self)

    def backup_account_keys(self, tag: str, folder_path: Path) -> bool:
        """把 tdata 目录下的密钥文件备份到配置中"""
        return TelegramKeyManager.backup_keys(tag, folder_path, self)

    def has_complete_keys(self, tag: str) -> bool:
        """检查某个账户是否同时存有 identity / info / key 三份密钥"""
        account = self.get_account(tag)
        return bool(account.get('key') and account.get('identity') and account.get('info'))

    # -- 环境扫描 --

    @staticmethod
    def scan_accounts_from_path(base_path: str, passcode: str = None) -> Dict[str, Dict[str, Any]]:
        """扫描指定路径下所有 Telegram 账户"""
        return TelegramEnvService.scan_accounts(base_path, passcode)

    def sync_all_account_paths(self) -> None:
        """重新扫描 base path，更新每个账户的实际文件夹路径"""
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

    # -- 批量操作 --

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """一次性更新多个配置字段，用 context manager 保证原子性"""
        with self:
            for field, value in updates.items():
                if hasattr(self, field):
                    setattr(self, field, value)

    # -- 工具方法 --

    def watch_time(self) -> str:
        """返回从 start_time 到现在的运行时长，格式化为中文"""
        start = self.start_time
        if start is None:
            return "0时0分0秒"
        return format_timedelta(datetime.now() - start)
