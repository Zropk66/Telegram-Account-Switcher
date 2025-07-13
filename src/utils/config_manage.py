# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import json
import os
import time
from copy import deepcopy
from pathlib import Path
from threading import RLock, Thread
from typing import Dict, Any, Optional

from src.utils.exceptions import TASConfigException


class ConfigField:
    """配置字段描述符类"""
    __slots__ = ('name', 'expected_type', '_cache')

    def __init__(self, name: str, expected_type: type):
        self.name = name
        self.expected_type = expected_type
        self._cache = {}

    def __get__(self, instance: Any, owner: type) -> Optional[Any]:
        instance_id = id(instance)

        if instance_id in self._cache:
            return self._cache[instance_id]

        value = instance._config.get(self.name)
        self._cache[instance_id] = value
        return value

    def __set__(self, instance: Any, value: Any) -> None:
        if not isinstance(value, self.expected_type):
            raise TypeError(
                f"{self.name} 需要 {self.expected_type.__name__}, "
                f"但实际得到的是 {type(value).__name__}"
            )

        instance_id = id(instance)
        self._cache[instance_id] = value

        instance._config[self.name] = value

        if not instance._batch_mode and self.name not in ['tag', 'process_status', 'complete']:
            instance._config_changed = True

    def clear_cache(self, instance: Any) -> None:
        """清除特定实例的缓存"""
        instance_id = id(instance)
        if instance_id in self._cache:
            del self._cache[instance_id]


class ConfigManage:
    """配置管理类"""
    client = ConfigField('client', str)
    path = ConfigField('path', str)
    default = ConfigField('default', str)
    tags = ConfigField('tags', list)
    log_output = ConfigField('log_output', bool)
    tag = ConfigField('tag', str)

    _instance = None
    _lock = RLock()
    _DEFAULT_CONFIG = {
        'client': 'Telegram.exe',
        'path': '',
        'default': '',
        'tags': [],
        'log_output': True,
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

        self._config_path = Path(os.getcwd()) / 'configs.json'
        self._temp_file = self._config_path.with_suffix('.tmp')

        self._config = self._load_config()

        self._batch_mode = False
        self._config_changed = False
        self._save_thread = None
        self._save_thread_running = True
        self.__initialized = True

        self._process_status = False
        self._complete = False

        self._start_auto_save()

    def __del__(self):
        """析构函数，停止自动保存线程"""
        self._save_thread_running = False
        if self._save_thread and self._save_thread.is_alive():
            self._save_thread.join(timeout=1.0)

        if self._config_changed:
            self._save_config(self._config)

    def __enter__(self):
        """进入批量更新模式"""
        self._batch_mode = True
        self._snapshot = deepcopy(self._config)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """退出批量更新模式"""
        self._batch_mode = False
        if exc_type is not None:
            self._config = self._snapshot
            self._config_changed = True
        else:
            self._config_changed = True

    def _start_auto_save(self) -> None:
        """启动自动保存线程"""
        self._save_thread = Thread(target=self._auto_save_worker, daemon=True)
        self._save_thread.start()

    def _auto_save_worker(self) -> None:
        """自动保存工作线程"""
        while self._save_thread_running:
            if self._config_changed:
                self._save_config(self._config)
            time.sleep(5)

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """批量更新配置项"""
        with self:
            for field, value in updates.items():
                setattr(self, field, value)

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if not self._config_path.exists():
                self._save_config(self._DEFAULT_CONFIG)

            with open(self._config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)

                if not all(k in loaded for k in self._DEFAULT_CONFIG):
                    raise json.JSONDecodeError("配置字段缺失", "", 0)

                return {**self._DEFAULT_CONFIG, **loaded}
        except (json.JSONDecodeError, IOError):
            self._save_config(self._DEFAULT_CONFIG)
            return self._DEFAULT_CONFIG.copy()

    def _save_config(self, configs: Dict[str, Any]) -> None:
        """保存配置文件"""
        if not self._config_path.parent.exists():
            raise TASConfigException('配置目录验证失败')

        try:
            config_copy = configs.copy()
            try:
                config_copy.pop('tag')
            except KeyError:
                pass

            with open(self._temp_file, 'w', encoding='utf-8') as f:
                json.dump(config_copy, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(self._temp_file, self._config_path)
            self._config_changed = False
        finally:
            if self._temp_file.exists():
                try:
                    self._temp_file.unlink()
                except OSError:
                    pass

    @property
    def process_status(self) -> bool:
        """获取进程状态"""
        return self._process_status

    @process_status.setter
    def process_status(self, value: bool) -> None:
        """设置进程状态"""
        if not isinstance(value, bool):
            raise TypeError(f"process_status 的类型必须为 {bool}")
        self._process_status = value

    @property
    def complete(self) -> bool:
        """获取程序完成状态"""
        return self._complete

    @complete.setter
    def complete(self, value: bool) -> None:
        """设置程序完成状态"""
        if not isinstance(value, bool):
            raise TypeError(f"complete 的类型必须为 {bool}")
        self._complete = value

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
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, ConfigField):
                attr.clear_cache(self)
