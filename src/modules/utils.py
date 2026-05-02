# -*- coding: utf-8 -*-
# @File ： utils.py
# @Time : 2025/8/6 00:02
# @Author : Zropk
from pathlib import Path


def search_file_in_dirs(directory, tag_name):
    """搜索目录下包含 tas_tag 标识的账户文件夹"""
    try:
        base_dir = Path(directory)
        if not base_dir.is_dir():
            return None

        for entry in base_dir.iterdir():
            if entry.is_dir():
                tas_tag_file = entry / "tas_tag"
                if tas_tag_file.is_file():
                    try:
                        if tas_tag_file.read_text(encoding="utf-8").strip() == tag_name:
                            return entry.name
                    except Exception:
                        pass
        return None
    except Exception as e:
        import logging
        logging.error(f"Search for tag {tag_name} failed: {e}")
        return None


def is_exists(base_path: str, target_tag: str) -> bool:
    """检查文件夹是否匹配目标标签"""
    if not base_path or not target_tag:
        return False
    try:
        folder = Path(base_path)
        tas_tag_file = folder / "tas_tag"
        if tas_tag_file.is_file():
            try:
                if tas_tag_file.read_text(encoding="utf-8").strip() == target_tag:
                    return True
            except Exception:
                pass
        return False
    except (PermissionError, OSError):
        return False


def format_timedelta(delta):
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}时{minutes}分{seconds}秒"
