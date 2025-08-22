# -*- coding: utf-8 -*-
# @File ： utils.py
# @Time : 2025/8/6 00:02
# @Author : Zropk
import os


def search_file_in_dirs(base_path: str, target_file: str):
    """在文件夹中查找目标文件并返回具体路径"""
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
        return os.path.exists(os.path.join(base_path, target_file))
    except (FileNotFoundError, PermissionError, TypeError):
        return False


def format_timedelta(delta):
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}时{minutes}分{seconds}秒"
