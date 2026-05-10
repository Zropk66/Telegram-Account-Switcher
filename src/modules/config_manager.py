# -*- coding: utf-8 -*-
import base64
import json
import os
import time
import weakref
from contextlib import suppress
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import RLock, Thread
from typing import Dict, Any, Optional, Type

from src.modules.env_service import TelegramEnvService


class RuntimeState:
    """应用程序临时运行时状态"""

    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.tag: str = ""
        self.force_key_login: bool = False
        self.process_status: bool = False
        self.complete: bool = False
        self.decrypted: bool = False
        self.password: str = ""
        self.has_backup: bool = False


class ConfigStorage:
    """配置持久化管理"""

    def __init__(self, config_path: Path, default_config: Dict[str, Any]):
        self._config_path = config_path
        self._temp_file = config_path.with_suffix(".tmp")
        self._default_config = default_config
        self._save_lock = RLock()
        self._save_thread_running = True
        self._config_changed = False
        self._batch = False
        self._config: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if not self._config_path.exists():
                self.save(self._default_config)

            with open(self._config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if not isinstance(loaded, dict):
                    loaded = {}
                self._config = {**self._default_config, **loaded}
                return self._config
        except (json.JSONDecodeError, IOError):
            self._config = self._default_config.copy()
            return self._config

    def save(self, configs: Dict[str, Any]) -> None:
        """持久化配置到文件"""
        with self._save_lock:
            try:
                self._config_path.parent.mkdir(parents=True, exist_ok=True)

                # 只保存持久化字段
                config_to_save = {
                    k: v for k, v in dict(configs).items() if k in self._default_config
                }

                with open(self._temp_file, "w", encoding="utf-8") as f:
                    json.dump(config_to_save, f, indent=4, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

                os.replace(self._temp_file, self._config_path)
                self._config_changed = False
            except Exception as e:
                with suppress(Exception):
                    from src.modules import Logger
                    Logger().error(f"保存配置文件失败: {e}")
            finally:
                with suppress(OSError):
                    if self._temp_file.exists():
                        self._temp_file.unlink()

    def start_auto_save(self, config_manage: 'ConfigManage') -> None:
        """启动自动保存线程"""

        def auto_save_worker():
            while self._save_thread_running:
                if self._config_changed and not self._batch:
                    self.save(config_manage._config)
                if config_manage.complete:
                    break
                time.sleep(5)

        Thread(target=auto_save_worker, daemon=True).start()

    def stop_auto_save(self):
        self._save_thread_running = False


class TelegramKeyManager:
    """Telegram 密钥管理逻辑"""

    @staticmethod
    def backup_keys(tag: str, folder_path: Path, config_manage: 'ConfigManage') -> bool:
        """从文件夹读取密钥并备份到配置中"""
        try:
            identity_path = folder_path / 'D877F783D5D3EF8Cs'
            info_path = folder_path / 'D877F783D5D3EF8C' / 'maps'
            key_path = folder_path / 'key_datas'

            if not (identity_path.exists() and info_path.exists() and key_path.exists()):
                return False

            data_identity = identity_path.read_bytes()
            data_info = info_path.read_bytes()
            data_key = key_path.read_bytes()

            account_data = config_manage.get_account(tag)
            account_data['info'] = base64.b64encode(data_info).decode()
            account_data['identity'] = base64.b64encode(data_identity).decode()
            account_data['key'] = base64.b64encode(data_key).decode()

            config_manage.set_account(tag, account_data)
            return True
        except (OSError, ValueError, TypeError):
            return False

    @staticmethod
    def login_with_keys(tag: str, tdata_path: str, config_manage: 'ConfigManage') -> bool:
        """使用备份的密钥模拟登录状态"""
        if not config_manage.has_complete_keys(tag):
            return False

        try:
            account = config_manage.get_account(tag)
            if not (account.get('key') and account.get('identity') and account.get('info')):
                return False
            try:
                tdata_dir = Path(tdata_path)
                tdata_dir.mkdir(parents=True, exist_ok=True)

                info_dir = tdata_dir / 'D877F783D5D3EF8C'
                info_dir.mkdir(parents=True, exist_ok=True)

                info_path = info_dir / 'maps'
                identity_path = tdata_dir / 'D877F783D5D3EF8Cs'
                key_path = tdata_dir / 'key_datas'

                info_path.write_bytes(base64.b64decode(account['info']))
                identity_path.write_bytes(base64.b64decode(account['identity']))
                key_path.write_bytes(base64.b64decode(account['key']))

                return True
            except (OSError, ValueError):
                return False

        except Exception:
            with suppress(Exception):
                from src.modules import Logger
                Logger().error("Key登录失败")
            return False


class ConfigField:
    """配置字段描述符"""

    __slots__ = ("name", "expected_type", "default_value", "_cache")

    def __init__(self, name: str, expected_type: type, default_value: Any = None):
        self.name = name
        self.expected_type = expected_type
        self.default_value = default_value
        self._cache = weakref.WeakKeyDictionary()

    def __get__(self, instance: Optional["ConfigManage"], owner: Type["ConfigManage"]) -> Any:
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

    def __set__(self, instance: "ConfigManage", value: Any) -> None:
        if value is not None and not isinstance(value, self.expected_type):
            raise TypeError(
                f"{self.name} expected {self.expected_type.__name__}, got {type(value).__name__}"
            )

        self._cache[instance] = value

        config = getattr(instance, "_config")
        config[self.name] = value

        instance._storage._config_changed = True
        if not instance._storage._batch:
            instance._storage.save(config)

    def clear_cache(self, instance: Any) -> None:
        if instance in self._cache:
            del self._cache[instance]


class ConfigManage:
    """配置管理类"""

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
            config_path=Path.cwd() / "configs.json",
            default_config=self._DEFAULT_CONFIG
        )
        self._config = self._storage.load()

        self.__initialized = True
        self._storage.start_auto_save(self)

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

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """批量更新配置项"""
        with self:
            for field, value in updates.items():
                if hasattr(self, field):
                    setattr(self, field, value)

    def watch_time(self) -> str:
        start = self.start_time
        if start is None:
            return "0时0分0秒"
        from src.modules.utils import format_timedelta
        return format_timedelta(datetime.now() - start)

    @property
    def start_time(self) -> Optional[datetime]:
        return self._runtime.start_time

    @start_time.setter
    def start_time(self, value: Optional[datetime]) -> None:
        self._runtime.start_time = value

    @property
    def tag(self) -> str:
        return self._runtime.tag

    @tag.setter
    def tag(self, value: str) -> None:
        self._runtime.tag = str(value) if value is not None else ""

    @property
    def force_key_login(self) -> bool:
        return self._runtime.force_key_login

    @force_key_login.setter
    def force_key_login(self, value: bool) -> None:
        self._runtime.force_key_login = bool(value)

    @property
    def process_status(self) -> bool:
        return self._runtime.process_status

    @process_status.setter
    def process_status(self, value: bool) -> None:
        self._runtime.process_status = bool(value)

    @property
    def complete(self) -> bool:
        return self._runtime.complete

    @complete.setter
    def complete(self, value: bool) -> None:
        self._runtime.complete = bool(value)

    @property
    def pwd(self) -> str:
        return self._runtime.password

    @pwd.setter
    def pwd(self, value: str) -> None:
        self._runtime.password = str(value) if value is not None else ""

    @property
    def decrypted(self) -> bool:
        return self._runtime.decrypted

    @decrypted.setter
    def decrypted(self, value: bool) -> None:
        self._runtime.decrypted = bool(value)

    @property
    def has_backup(self) -> bool:
        return self.has_complete_keys(self.tag)

    @property
    def configs(self) -> Dict[str, Any]:
        return self._config.copy()

    @property
    def config_file(self) -> Path:
        return self._storage._config_path

    @property
    def default_configs(self) -> Dict[str, Any]:
        return self._DEFAULT_CONFIG.copy()

    def clear_cache(self) -> None:
        cls = type(self)
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, ConfigField):
                attr.clear_cache(self)

    def get_all_accounts(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.tags)

    def get_account(self, tag: str) -> Dict[str, Any]:
        tags: Dict[str, Dict[str, Any]] = self.tags
        return tags.get(tag, {'id': '', 'folder': '', 'info': '', 'identity': '', 'key': ''})

    def set_account(self, tag: str, account_data: Dict[str, Any]) -> None:
        with self._lock:
            tags = dict(self.tags)
            tags[tag] = account_data
            self.tags = tags

    def remove_account(self, tag: str) -> None:
        tags = dict(self.tags)
        if tag in tags:
            del tags[tag]
            self.tags = tags

    def get_tag_list(self) -> list:
        return list(self.tags.keys())

    def login_with_keys(self, tag: str, tdata_path: str) -> bool:
        return TelegramKeyManager.login_with_keys(tag, tdata_path, self)

    @staticmethod
    def scan_accounts_from_path(base_path: str, passcode: str = None) -> Dict[str, Dict[str, Any]]:
        return TelegramEnvService.scan_accounts(base_path, passcode)

    def has_complete_keys(self, tag: str) -> bool:
        account = self.get_account(tag)
        return bool(account.get('key') and account.get('identity') and account.get('info'))

    def backup_account_keys(self, tag: str, folder_path: Path) -> bool:
        return TelegramKeyManager.backup_keys(tag, folder_path, self)

    def sync_all_account_paths(self) -> None:
        if not self.path or not os.path.isdir(self.path):
            return

        updated_tags, changed = TelegramEnvService.sync_account_folders(self.path, self.tags)
        if changed:
            self.tags = updated_tags
