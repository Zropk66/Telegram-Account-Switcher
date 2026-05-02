# -*- coding: utf-8 -*-
import base64
import json
import os
import pathlib
import time
import weakref
from contextlib import suppress
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import RLock, Thread
from typing import Dict, Any, Optional, Type

from src.modules.utils import format_timedelta, search_file_in_dirs


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

        # Use getattr to avoid lint warnings on unresolved protected members
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

        # Use getattr/setattr or internal dict
        config = getattr(instance, "_config")
        config[self.name] = value

        setattr(instance, "_config_changed", True)
        if not getattr(instance, "_batch", False):
            # Resolve the protected method call by using the instance method
            save_func = getattr(instance, "_save_config")
            save_func(config)

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

        self._lock = RLock()
        self._save_lock = RLock()
        self._batch = False
        self._config_changed = False
        self._save_thread = None
        self._save_thread_running = True

        self._process_status: bool = False
        self._complete: bool = False
        self._decrypted: bool = False
        self._has_backup: bool = False
        self._password: str = ""
        self._tag: str = ""
        self._force_key_login: bool = False
        self._start_time: Optional[datetime] = None

        self._config_path = Path.cwd() / "configs.json"
        self._temp_file = self._config_path.with_suffix(".tmp")
        self._config = self._load_config()

        self.__initialized = True
        self._start_auto_save()

    def __del__(self):
        """停止自动保存线程"""
        self._save_thread_running = False
        if hasattr(self, '_save_thread') and self._save_thread and self._save_thread.is_alive():
            with suppress(RuntimeError):
                self._save_thread.join(timeout=1.0)

        if hasattr(self, '_config_changed') and self._config_changed:
            self._save_config(self._config)

    def __enter__(self):
        """开启批量更新"""
        self._batch = True
        self._snapshot = deepcopy(self._config)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """退出批量更新并保存"""
        self._batch = False
        if exc_type is not None:
            self._config = self._snapshot
            self._config_changed = True
        else:
            if self._config_changed:
                self._save_config(self._config)

    def _start_auto_save(self) -> None:
        self._save_thread = Thread(target=self._auto_save_worker, daemon=True)
        self._save_thread.start()

    def _auto_save_worker(self) -> None:
        """自动保存工作线程"""
        while self._save_thread_running:
            if self._config_changed and not self._batch:
                self._save_config(self._config)
            if self._complete:
                break
            time.sleep(5)

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """批量更新配置项"""
        with self:
            for field, value in updates.items():
                if hasattr(self, field):
                    setattr(self, field, value)

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if not self._config_path.exists():
                self._save_config(self._DEFAULT_CONFIG)

            with open(self._config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if not isinstance(loaded, dict):
                    loaded = {}
                
                return {**self._DEFAULT_CONFIG, **loaded}
        except (json.JSONDecodeError, IOError):
            return self._DEFAULT_CONFIG.copy()

    def _save_config(self, configs: Dict[str, Any]) -> None:
        """持久化配置到文件"""
        with self._save_lock:
            try:
                self._config_path.parent.mkdir(parents=True, exist_ok=True)

                # 只保存持久化字段
                config_to_save = {
                    k: v for k, v in dict(configs).items() if k in self._DEFAULT_CONFIG
                }

                with open(self._temp_file, "w", encoding="utf-8") as f:
                    json.dump(config_to_save, f, indent=4, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

                os.replace(self._temp_file, self._config_path)
                self._config_changed = False
            except OSError as e:
                with suppress(Exception):
                    from src.modules import Logger
                    Logger().error(f"保存配置文件失败: {e}")

            except Exception:
                with suppress(Exception):
                    from src.modules import Logger
                    Logger().error("保存配置时发生未知错误")

            finally:
                with suppress(OSError):
                    if self._temp_file.exists():
                        self._temp_file.unlink()

    def watch_time(self) -> str:
        start = self.start_time
        if start is None:
            return "0时0分0秒"
        return format_timedelta(datetime.now() - start)

    @property
    def start_time(self) -> Optional[datetime]:
        """获取监控开始时间"""
        return self._start_time

    @start_time.setter
    def start_time(self, value: Optional[datetime]) -> None:
        """设置监控开始时间"""
        self._start_time = value

    @property
    def tag(self) -> str:
        """获取临时标签"""
        return self._tag

    @tag.setter
    def tag(self, value: str) -> None:
        """设置临时标签"""
        self._tag = str(value) if value is not None else ""

    @property
    def force_key_login(self) -> bool:
        """获取是否强制使用密钥登录"""
        return self._force_key_login

    @force_key_login.setter
    def force_key_login(self, value: bool) -> None:
        """设置是否强制使用密钥登录"""
        self._force_key_login = bool(value)

    @property
    def process_status(self) -> bool:
        """获取进程状态"""
        return self._process_status

    @process_status.setter
    def process_status(self, value: bool) -> None:
        """设置进程状态"""
        self._process_status = bool(value)

    @property
    def complete(self) -> bool:
        """获取程序完成状态"""
        return self._complete

    @complete.setter
    def complete(self, value: bool) -> None:
        """设置程序完成状态"""
        self._complete = bool(value)

    @property
    def pwd(self) -> str:
        """获取解密密钥"""
        return self._password

    @pwd.setter
    def pwd(self, value: str) -> None:
        """设置解密密钥"""
        self._password = str(value) if value is not None else ""

    @property
    def decrypted(self) -> bool:
        """获取解密状态"""
        return self._decrypted

    @decrypted.setter
    def decrypted(self, value: bool) -> None:
        """设置解密状态"""
        self._decrypted = bool(value)

    @property
    def has_backup(self) -> bool:
        """获取所有关键密钥是否已在配置中备份"""
        return self.has_complete_keys(self.tag)

    @property
    def configs(self) -> Dict[str, Any]:
        """获取所有配置项"""
        return self._config.copy()

    @property
    def config_file(self) -> Path:
        """获取配置文件路径"""
        return Path(self._config_path)

    @property
    def default_configs(self) -> Dict[str, Any]:
        """获取默认配置项"""
        return self._DEFAULT_CONFIG.copy()

    def clear_cache(self) -> None:
        """清除所有字段的缓存"""
        cls = type(self)
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, ConfigField):
                attr.clear_cache(self)

    def get_all_accounts(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.tags)

    def get_account(self, tag: str) -> Dict[str, Any]:
        """
        获取指定账户的数据
        """
        tags: Dict[str, Dict[str, Any]] = self.tags
        account = tags.get(tag, {'id': '', 'folder': '', 'info': '', 'identity': '', 'key': ''})
        return account

    def set_account(self, tag: str, account_data: Dict[str, Any]) -> None:
        """
        设置账户数据
        """
        with self._lock:
            tags = dict(self.tags)  # 获取副本
            tags[tag] = account_data
            self.tags = tags

    def remove_account(self, tag: str) -> None:
        """
        删除账户
        """
        tags = dict(self.tags)
        if tag in tags:
            del tags[tag]
            self.tags = tags

    def get_tag_list(self) -> list:
        """获取所有已注册的标签列表"""
        return list(self.tags.keys())

    def login_with_keys(self, tag: str, tdata_path: str) -> bool:
        if not self.has_complete_keys(tag):
            return False

        try:
            account = self.get_account(tag)
            if not (account.get('key') and account.get('identity') and account.get('info')):
                return False
            try:
                tdata_dir = pathlib.Path(tdata_path)
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

    @staticmethod
    def scan_accounts_from_path(base_path: str, passcode: str = None) -> Dict[str, Dict[str, Any]]:
        """
        从指定路径扫描账户
        """
        import src.modules.telegram_data_decrypter.main as tdd
        result: Dict[str, Dict[str, Any]] = {}

        try:
            base = Path(base_path)
            if not base.is_dir():
                return result

            suspected_folders = []
            for entry in base.iterdir():
                if not entry.is_dir():
                    continue
                
                if (entry / 'key_datas').exists() or \
                   (entry / 'settingss').exists() or \
                   (entry / 'D877F783D5D3EF8Cs').exists() or \
                   (entry / 'D877F783D5D3EF8C' / 'maps').exists():
                    suspected_folders.append(entry)

            for folder in suspected_folders:
                folder_name = folder.name
                user_id = ""
                
                try:
                    accounts = tdd.decrypt_accounts(folder, passcode)
                    if accounts and accounts[0].get('user_id'):
                        user_id = str(accounts[0].get('user_id'))
                except Exception:
                    pass

                tag_name = folder_name
                tas_tag_file = folder / "tas_tag"
                if tas_tag_file.is_file():
                    with suppress(Exception):
                        content = tas_tag_file.read_text(encoding="utf-8").strip()
                        if content:
                            tag_name = content

                account_data = {
                    'id': user_id,
                    'tag': tag_name,
                    'folder': folder_name,
                    'info': '',
                    'identity': '',
                    'key': ''
                }

                # 读取密钥数据
                info_path = folder / 'D877F783D5D3EF8C' / 'maps'
                identity_path = folder / 'D877F783D5D3EF8Cs'
                key_path = folder / 'key_datas'

                if info_path.exists():
                    with suppress(Exception):
                        account_data['info'] = base64.b64encode(info_path.read_bytes()).decode()
                if identity_path.exists():
                    with suppress(Exception):
                        account_data['identity'] = base64.b64encode(identity_path.read_bytes()).decode()
                if key_path.exists():
                    with suppress(Exception):
                        account_data['key'] = base64.b64encode(key_path.read_bytes()).decode()

                result[folder_name] = account_data

        except Exception:
            with suppress(Exception):
                from src.modules import Logger
                Logger().error("扫描账户过程中发生严重异常")

        return result

    def has_complete_keys(self, tag: str) -> bool:
        """检查密钥是否完整"""
        account = self.get_account(tag)
        return bool(account.get('key') and account.get('identity') and account.get('info'))

    def backup_account_keys(self, tag: str, folder_path: Path) -> bool:
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

            account_data = self.get_account(tag)
            account_data['info'] = base64.b64encode(data_info).decode()
            account_data['identity'] = base64.b64encode(data_identity).decode()
            account_data['key'] = base64.b64encode(data_key).decode()

            self.set_account(tag, account_data)
            return True
        except (OSError, ValueError, TypeError):
            return False

    def sync_all_account_paths(self) -> None:
        """同步磁盘路径到配置"""
        if not self.path or not os.path.isdir(self.path):
            return

        with self:
            updated_tags = deepcopy(self.tags)
            changed = False
            for tag, info in updated_tags.items():
                real_folder = search_file_in_dirs(self.path, tag)
                if real_folder and info.get("folder") != real_folder:
                    info["folder"] = real_folder
                    changed = True

            if changed:
                self.tags = updated_tags
