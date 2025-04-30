import json
import os
import random
import sys
import time

from src.utils.logger import logger
from src.utils.process_utils import handle_process, system_exit


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
        system_exit()
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
        handle_process(client=client, mode='kill')
        time.sleep(1)
        modify_file('restore')
    except (FileNotFoundError, PermissionError):
        logger.error('恢复帐户时出现错误.')


def config_helper(field: str, mode: str, value=None):
    """配置管理器"""
    try:
        supportKey = {'client': '', 'path': '', 'args': [], 'default': ''}
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
