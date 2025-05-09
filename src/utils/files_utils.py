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
from typing import Any, Dict
from pathlib import Path

from src.utils.logger import logger
from src.utils.process_utils import safe_exit
from utils.process_utils import try_kill_process


def search_target_file_in_directories(base_path: str, target_file: str):
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


def modify_file(mode: str, retries=0, max_retries=3):
    """修改tdata文件，实现不同账号登录"""
    path = config_helper(field='path', mode='r')
    default = config_helper(field='default', mode='r')
    arg = sys.argv[-1]
    if retries >= max_retries:
        safe_exit()
    random_str = ''.join(random.sample('ABCDEFG', 5))
    temp = f'tdata-{random_str}'
    try:
        if mode == 'restore':
            try:
                os.rename(os.path.join(path, 'tdata'), os.path.join(path, temp))
            except FileNotFoundError:
                pass
            os.rename(
                os.path.join(path, search_target_file_in_directories(path, default)),
                os.path.join(path, 'tdata'))
            logger.info('恢复账户.')
            return True
        elif mode == 'modify':
            try:
                arg_dir = os.path.join(path, search_target_file_in_directories(path, arg))
            except TypeError:
                return True
            try:
                os.rename(os.path.join(path, 'tdata'), os.path.join(path, temp))
            except FileNotFoundError:
                pass
            os.rename(arg_dir, os.path.join(path, 'tdata'))
            logger.info('账户切换.')
            return True
        logger.error(f"模式 '{mode}' 无法执行，文件状态不符合要求.")
        return False
    except (FileNotFoundError, PermissionError) as e:
        logger.error(f"文件操作失败: {e}, 重试... ({retries + 1}/{max_retries})")
        time.sleep(1)
        return modify_file(mode, retries + 1, max_retries)


def restore_file():
    """程序结束时自动还原"""
    try:
        client = config_helper(field='client', mode='r')
        try_kill_process(client)
        time.sleep(1)
        modify_file('restore')
    except (FileNotFoundError, PermissionError):
        logger.error('恢复帐户时出现错误.')


def config_helper(field: str, mode: str, value=None):
    """配置管理器"""
    if not isinstance(field, str):
        raise TypeError(f"字段类型应为 str，实际传入：{type(field)}")
    if not isinstance(mode, str) or len(mode) != 1:
        raise ValueError("模式参数格式错误")
    if mode == 'w' and value is None:
        raise ValueError("写入模式必须提供 value 参数")
    try:
        supportKey = {'client': '', 'path': '', 'tags': [], 'default': ''}
        supportMode = {'w', 'r'}

        if field == 'defaultMain':
            field = 'default'
        if mode not in supportMode:
            raise ValueError(f"不支持的模式： {mode}，仅支持 'r' 或 'w' 模式")

        if field not in supportKey.keys():
            raise ValueError(f"不支持的字段: {field}")
        from src.main import WORK_PATH
        configPath = os.path.join(WORK_PATH, "configs.json")
        if not os.path.exists(configPath):
            with open(configPath, 'w', encoding='utf-8') as f:
                f.write('')

        configs = {}
        if os.path.exists(configPath):
            try:
                with open(configPath, 'r', encoding='utf-8') as f:
                    data = f.read()
                    if not (data is None) or not data == '':
                        configs = json.loads(data)
            except json.decoder.JSONDecodeError:
                configs = {}

        configs = {k: v for k, v in configs.items() if k in supportKey.keys()}

        if mode == 'r':
            for k, v in configs.items():
                if k == field:
                    if not (value is None) or not value == '':
                        return v
            configs[field] = supportKey.get(field)

            with open(configPath, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=4)
            return configs.get(field)

        try:
            if not isinstance(configs[field], list) and field == 'args':
                configs[field] = []
            elif field == 'args' and value != '':
                for arg in value:
                    if arg not in configs[field]:
                        configs[field].append(arg)
            else:
                configs[field] = value
            if value != '' or value == []:
                with open(configPath, 'w', encoding='utf-8') as f:
                    json.dump(configs, f, indent=4)
            return None
        except Exception as e:
            raise IOError(f"写入配置失败: {str(e)}") from e
    except Exception:
        raise IOError('文件操作出现未知错误.')


class config_manager:
    """配置管理类，实现原子化操作和类型校验"""

    _DEFAULT_CONFIG = {
        'client': 'Telegram.exe',
        'path': '',
        'default': '',
        'tags': []
    }

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """增强型单例初始化"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.__init_flag = False
                    cls._instance.__initialize()
        return cls._instance


    def __initialize(self) -> None:
        """延迟初始化方法"""
        self._config_path = Path(os.path.join(os.getcwd(), 'configs.json'))
        self._temp_file = self._config_path.with_suffix('.tmp')
        self._config = self._load_config()
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self.__init_flag = True
        self.logger = logger
        self.tag = ''

    def _load_config(self) -> Dict[str, Any]:
        """安全加载配置（自动修复损坏配置）"""
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
        """原子化写入配置"""
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
        """
        批量保存多个配置字段（原子化操作）

        参数：
        fields: 需更新的字段字典，键为字段名，值为新数据

        异常：
        KeyError - 包含无效字段时抛出
        TypeError - 字段类型不匹配时抛出
        IOError - 文件写入失败时抛出
        """
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

    def get_all_fields(self, with_default: bool = False) -> Dict[str, Any]:
        """
        获取全部配置项（深度拷贝保障数据安全）

        参数：
        with_default - 是否包含默认值字段（默认False时仅返回用户修改过的字段）

        返回：
        配置字典（包含类型转换后的值）

        异常：
        ConfigError - 当配置完整性校验失败时抛出
        """
        configs = deepcopy(self._config)
        if not with_default:
            return {
                k: v for k, v in configs.items()
                if v != self._DEFAULT_CONFIG.get(k)
            }
        return configs


    def get(self, field: str) -> Any:
        """
        获取配置项值
        :param field: 配置字段名
        :return: 配置值，不存在时返回默认值
        """
        if field == 'tag':
            return self.tag
        if field not in self._DEFAULT_CONFIG:
            raise KeyError(f"无效配置项: {field}")
        return self._config.get(field, self._DEFAULT_CONFIG[field])

    def set(self, field: str, value: Any) -> None:
        """
        设置配置项值
        :param field: 配置字段名
        :param value: 要设置的值
        """
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
        """
        删除配置项，恢复默认值
        :param field: 配置字段名
        """
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
