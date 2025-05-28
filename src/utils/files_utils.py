# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import json
import os
import random
import sys
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from src.utils.logger import logger


def search_file_in_dirs(base_path: str, target_file: str):
    """检测文件夹中是否存在指定文件"""
    if not os.path.isdir(base_path):
        return ''

    for entry in os.scandir(base_path):
        if entry.is_dir():
            filePath = os.path.join(entry.path, target_file)
            if os.path.isfile(filePath):
                return entry.name
    return ''


def is_exists(base_path: str, target_file: str):
    """判断文件夹中是否存在目标文件"""
    try:
        if os.path.exists(os.path.join(base_path, target_file)):
            return True
        else:
            return False
    except (FileNotFoundError, PermissionError, TypeError):
        return False


def account_switch(mode: str, retries=0, max_retries=5):
    """修改tdata文件，实现不同账号登录"""
    path = config_manager().get('path')
    default = config_manager().get('default')
    arg = sys.argv[-1]
    if retries >= max_retries:
        from src.utils.process_utils import safe_exit
        safe_exit()
    random_str = ''.join(random.sample('ABCDEFG', 5))
    temp = f'tdata-{random_str}'
    try:
        if mode == 'restore':
            if switch_to_default(path, default, temp):
                logger.info('账户已切换为默认账户.')
                return True
            else:
                return False
        elif mode == 'switch':
            if switch_to_target(path, arg, temp):
                logger.info(f"已切换为目标账户 -> '{arg}'.")
                return True
            else:
                return False
        raise TypeError(f"模式 '{mode}' 未定义.")
    except PermissionError:
        logger.error(f"权限不足, 正在重试... ({retries + 1}/{max_retries})")
        time.sleep(1)
        return account_switch(mode, retries + 1, max_retries)

def switch_to_default(path, default, temp):
    """切换回默认账户"""
    try:
        os.rename(os.path.join(path, 'tdata'), os.path.join(path, temp))
    except FileNotFoundError:
        pass
    os.rename(
        os.path.join(path, search_file_in_dirs(path, default)),
        os.path.join(path, 'tdata'))
    return True

def switch_to_target(path, arg, temp):
    """切换为目标账户"""
    try:
        arg_dir = os.path.join(path, search_file_in_dirs(path, arg))
    except TypeError:
        return True
    os.rename(os.path.join(path, 'tdata'), os.path.join(path, temp))
    os.rename(arg_dir, os.path.join(path, 'tdata'))
    return True

def recovery():
    """强制恢复为默认账户"""
    try:
        client = config_manager().get('client')
        from src.utils.process_utils import try_kill_process
        try_kill_process(client)
        time.sleep(1)
        time.sleep(1)
        account_switch('restore')
    except (FileNotFoundError, PermissionError):
        logger.error('恢复帐户时出现错误.')


class config_manager:
    """配置管理类，实现原子化操作和类型校验"""

    _DEFAULT_CONFIG = {
        'client': 'Telegram.exe',
        'path': '',
        'default': '',
        'tags': [],
        'log_output': True,
    }

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """初始化"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.__init_flag = False
                    cls._instance.__initialize()
        return cls._instance

    def __initialize(self) -> None:
        """初始化"""
        self._config_path = Path(os.path.join(os.getcwd(), 'configs.json'))
        self._temp_file = self._config_path.with_suffix('.tmp')
        self._config = self._load_config()
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self.__init_flag = True
        self.logger = logger
        self.tag = ''

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
            print(f"配置损坏，恢复默认值: {str(e)}")
            self._save_config(self._DEFAULT_CONFIG)
            return self._DEFAULT_CONFIG.copy()

    def _save_config(self, config: Dict) -> None:
        """写入配置"""
        try:
            with open(self._temp_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(self._temp_file, self._config_path)
        finally:
            if self._temp_file.exists():
                self._temp_file.unlink()

    def save_multiple_fields(self, fields: Dict[str, Any]) -> None:
        """一次性保存多个配置字段"""
        invalid_fields = [k for k in fields if k not in self._DEFAULT_CONFIG]
        if invalid_fields:
            raise KeyError(f"无效配置字段: {', '.join(invalid_fields)}")

        type_errors = []
        for field, value in fields.items():
            expected_type = type(self._DEFAULT_CONFIG[field])
            if not isinstance(value, expected_type):
                type_errors.append(
                    f"字段 '{field}' 类型错误: 应为 {expected_type}, 实际为 {type(value)}"
                )
        if type_errors:
            raise TypeError("\n".join(type_errors))

        try:
            self._config.update(fields)

            self._save_config(self._config)

        except Exception as e:
            raise self.ConfigError(f"批量保存失败: {str(e)}") from e

    def get_all(self, with_default: bool = False) -> Dict[str, Any]:
        """获取全部配置项"""
        configs = deepcopy(self._config)
        if not with_default:
            return {
                k: v for k, v in configs.items()
                if v != self._DEFAULT_CONFIG.get(k)
            }
        return configs

    def get(self, field: str) -> Any:
        """获取配置项值"""
        if field == 'tag':
            return self.tag
        if field not in self._DEFAULT_CONFIG:
            raise KeyError(f"无效配置项: {field}")
        return self._config.get(field, self._DEFAULT_CONFIG[field])

    def set(self, field: str, value: Any) -> None:
        """设置配置项值"""
        if field == 'tag':
            self.tag = value
            return
        if field not in self._DEFAULT_CONFIG:
            raise KeyError(f"无效配置项: {field}")

        expected_type = type(self._DEFAULT_CONFIG[field])
        if not isinstance(value, expected_type):
            raise TypeError(
                f"{field} 类型错误，应为 {expected_type}，实际为 {type(value)}"
            )

        self._config[field] = value
        self._save_config(self._config)

    def delete(self, field: str) -> None:
        """删除配置项，恢复默认值"""
        if field not in self._DEFAULT_CONFIG:
            raise KeyError(f"无效配置项: {field}")

        self._config[field] = self._DEFAULT_CONFIG[field]
        self._save_config(self._config)

    @property
    def config_path(self) -> Path:
        """返回配置文件路径"""
        return self._config_path

    class ConfigError(Exception):
        """自定义配置异常"""
        pass
