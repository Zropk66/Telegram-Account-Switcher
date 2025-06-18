# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import random
import sys
import time

from src.utils.config_manage import ConfigManage


def search_file_in_dirs(base_path: str, target_file: str):
    """检测文件夹中是否存在指定文件"""
    if not os.path.isdir(base_path):
        return ''

    for entry in os.scandir(base_path):
        if entry.is_dir():
            file_path = os.path.join(entry.path, target_file)
            if os.path.isfile(file_path):
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
    """控制账户的切换与还原"""
    config = ConfigManage()
    tag = sys.argv[-1]
    if retries >= max_retries:
        raise PermissionError('权限不足，如法切换账户.')
    random_str = ''.join(random.sample('ABCDEFG', 5))
    temp = f'tdata-{random_str}'
    try:
        if mode == 'restore':
            if switch_to_default(config.path, config.default, temp):
                return True
            else:
                return False
        elif mode == 'switch':
            if switch_to_target(config.path, tag, temp):
                return True
            else:
                return False
        raise TypeError(f"模式 '{mode}' 未定义.")
    except PermissionError:
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
        target_dir = os.path.join(path, search_file_in_dirs(path, arg))
    except TypeError:
        return True
    os.rename(os.path.join(path, 'tdata'), os.path.join(path, temp))
    os.rename(target_dir, os.path.join(path, 'tdata'))
    return True


def recovery():
    """强制恢复为默认账户"""
    try:
        from src.utils.process_utils import try_kill_process
        try_kill_process(ConfigManage().client)
        time.sleep(1)
        account_switch('restore')
    except (FileNotFoundError, PermissionError):
        raise IOError('强制恢复时出现错误.')


import os

def validate_path(path: str) -> bool:
    """路径有效性验证"""
    return os.path.exists(path) and os.path.isfile(path)
