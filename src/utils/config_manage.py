import json
import os
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Dict, Any


class ConfigField:
    __slots__ = ('name', 'expected_type')

    def __init__(self, name, expected_type):
        self.name = name
        self.expected_type = expected_type

    def __get__(self, instance, owner):
        if self.name == 'tag':
            return instance.temp_tag
        return instance._config.get(self.name)

    def __set__(self, instance, value):
        if not isinstance(value, self.expected_type):
            raise self._create_type_error()
        if self.name == 'tag':
            instance.temp_tag = value
        instance._config[self.name] = value
        if not instance._batch_mode:
            instance._save_config(instance._config)

    def _create_type_error(self):
        return TypeError(
            f"{self.name} requires {self.expected_type.__name__}, "
            f"got {self.expected_type}"
        )


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
        if self.__initialized:
            return

        self._config_path = Path(os.getcwd()) / 'configs.json'
        self._temp_file = self._config_path.with_suffix('.tmp')
        self._config = self._load_config()
        self._batch_mode = False
        self.__initialized = True
        self.temp_tag = ''

    def __enter__(self):
        self._batch_mode = True
        self._snapshot = deepcopy(self._config)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._batch_mode = False
        if exc_type is not None:
            self._config = self._snapshot
            self._save_config(self._config)
        else:
            self._save_config(self._config)

    def batch_update(self, updates: Dict[str, Any]) -> None:
        with self:
            for field, value in updates.items():
                setattr(self, field, value)

    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        try:
            if not self._config_path.exists():
                self._save_config(self._DEFAULT_CONFIG)

            with open(self._config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if not all(k in loaded for k in self._DEFAULT_CONFIG):
                    raise json.JSONDecodeError("字段缺失", "", 0)
                return {**self._DEFAULT_CONFIG, **loaded}
        except (json.JSONDecodeError, IOError) as e:
            self._save_config(self._DEFAULT_CONFIG)
            return self._DEFAULT_CONFIG.copy()

    def _save_config(self, configs: Dict) -> None:
        """写入配置"""
        if not self._config_path.parent.exists():
            raise ConfigError('E101', 'path', '配置目录路径验证失败')
        try:
            try:
                configs.pop('tag')
            except KeyError:
                pass
            with open(self._temp_file, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(self._temp_file, self._config_path)
        finally:
            if self._temp_file.exists():
                self._temp_file.unlink()

    @property
    def configs(self) -> Dict[str, Any]:
        """获取全部配置项"""
        return self._config.copy()

    @property
    def default_configs(self):
        """获取默认配置项"""
        return self._DEFAULT_CONFIG.copy()

    @property
    def config_path(self) -> Path:
        """返回配置文件路径"""
        return self._config_path


class ConfigError(Exception):
    def __init__(self, code: str, message: str, field: str = None):
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"[{code}] {message}")

    @classmethod
    def from_io_error(cls, error: IOError):
        return cls(
            code="E100",
            message=f"文件操作失败: {str(error)}",
            field="_config_path"
        )
