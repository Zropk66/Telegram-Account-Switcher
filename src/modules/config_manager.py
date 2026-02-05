# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
from typing import Dict, Any
from threading import RLock, Thread
from contextlib import suppress
from copy import deepcopy
from pathlib import Path
import json
import time
import os
import weakref


class ConfigField:
    """配置字段描述符类"""

    __slots__ = ("name", "expected_type", "default_value", "_cache")

    def __init__(self, name: str, expected_type: type, default_value: Any = None):
        self.name = name
        self.expected_type = expected_type
        self.default_value = default_value
        self._cache = weakref.WeakKeyDictionary()

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            return self

        if instance in self._cache:
            return self._cache[instance]

        value = instance._config.get(self.name)
        if value is None:
            value = self.default_value

        if value is not None and not isinstance(value, self.expected_type):
            try:
                if self.expected_type is list and isinstance(value, str):
                    value = json.loads(value)
                else:
                    value = self.expected_type(value)
            except (ValueError, TypeError, json.JSONDecodeError):
                value = self.default_value

        self._cache[instance] = value
        return value

    def __set__(self, instance: Any, value: Any) -> None:
        if value is not None and not isinstance(value, self.expected_type):
            raise TypeError(
                f"{self.name} 需要 {self.expected_type.__name__}, "
                f"但实际得到的是 {type(value).__name__}"
            )

        self._cache[instance] = value

        instance._config[self.name] = value
        instance._config_changed = True
        if not getattr(instance, "_batch", False):
            instance._save_config(instance._config)

    def clear_cache(self, instance: Any) -> None:
        """清除特定实例的缓存"""
        if instance in self._cache:
            del self._cache[instance]


class ConfigManage:
    """配置管理类"""

    client = ConfigField("client", str, "Telegram.exe")
    path = ConfigField("path", str, "")
    default = ConfigField("default", str, "")
    tags = ConfigField("tags", list, [])
    log_output = ConfigField("log_output", bool, True)

    _instance = None
    _lock = RLock()
    _DEFAULT_CONFIG = {
        "client": "Telegram.exe",
        "path": "",
        "default": "",
        "tags": [],
        "log_output": True,
    }

    def __new__(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
                cls._instance.__initialized = False
        return cls._instance

    def __init__(self):
        """初始化"""
        if self.__initialized:
            return

        self._config_path = Path(os.getcwd()) / "configs.json"
        self._temp_file = self._config_path.with_suffix(".tmp")

        self._config = self._load_config()

        self._batch = False
        self._config_changed = False
        self._save_thread = None
        self._save_thread_running = True

        # 运行时状态
        self._process_status: bool = False
        self._complete: bool = False
        self._decrypted: bool = False
        self._has_backup: bool = False
        self._password: str = ""
        self._tag: str = ""

        self.__initialized = True
        self._start_auto_save()

    def __del__(self):
        """停止自动保存线程"""
        self._save_thread_running = False
        if self._save_thread and self._save_thread.is_alive():
            with suppress(RuntimeError):
                self._save_thread.join(timeout=1.0)

        if self._config_changed:
            self._save_config(self._config)

    def __enter__(self):
        """进入批量更新模式"""
        self._batch = True
        self._snapshot = deepcopy(self._config)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """退出批量更新模式"""
        self._batch = False
        if exc_type is not None:
            self._config = self._snapshot
            self._config_changed = True
        else:
            if self._config_changed:
                self._save_config(self._config)

    def _start_auto_save(self) -> None:
        """启动自动保存线程"""
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
        """保存配置文件"""
        try:
            # 确保目录存在
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            # 只保存持久化字段
            config_to_save = {
                k: v for k, v in configs.items() if k in self._DEFAULT_CONFIG
            }

            with open(self._temp_file, "w", encoding="utf-8") as f:
                json.dump(config_to_save, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(self._temp_file, self._config_path)
            self._config_changed = False
        except Exception:
            # 静默失败或记录日志，避免阻塞主流程
            pass
        finally:
            with suppress(OSError):
                if self._temp_file.exists():
                    self._temp_file.unlink()

    @property
    def tag(self) -> str:
        """获取临时标签"""
        return self._tag

    @tag.setter
    def tag(self, value: str) -> None:
        """设置临时标签"""
        self._tag = str(value) if value is not None else ""

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
        """获取备份状态"""
        return self._has_backup

    @has_backup.setter
    def has_backup(self, value: bool) -> None:
        """设置备份状态"""
        self._has_backup = bool(value)

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
