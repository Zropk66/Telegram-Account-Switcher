# -*- coding: utf-8 -*-
# @File    : config.py
# @Time    : 2026/5/10 18:07
# @Author  : Zropk

"""
配置文件
存放应用中的常量、路径等硬编码字符串
"""

from pathlib import Path


class PathConfig:
    """路径配置"""

    # 文件夹名称常量
    IDENTITY_FOLDER = 'D877F783D5D3EF8Cs'
    INFO_SUBFOLDER = 'maps'
    KEY_FOLDER = 'key_datas'

    @classmethod
    def get_identity_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """
        获取身份文件路径
        
        Args:
            folder_path: 基础文件夹路径
            auto_create: 是否自动创建文件夹（包括父目录）
            
        Returns:
            Path: 身份文件路径
        """
        path = folder_path / cls.IDENTITY_FOLDER
        if auto_create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_info_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """
        获取信息文件路径
        
        Args:
            folder_path: 基础文件夹路径
            auto_create: 是否自动创建文件夹（包括父目录）
            
        Returns:
            Path: 信息文件路径
        """
        path = folder_path / 'D877F783D5D3EF8C' / cls.INFO_SUBFOLDER
        if auto_create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_key_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """
        获取密钥文件路径
        
        Args:
            folder_path: 基础文件夹路径
            auto_create: 是否自动创建文件夹（包括父目录）
            
        Returns:
            Path: 密钥文件路径
        """
        path = folder_path / cls.KEY_FOLDER
        if auto_create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_all_paths(cls, folder_path: Path) -> dict:
        """
        传入基础路径，返回所有子路径

        Args:
            folder_path: 基础文件夹路径

        Returns:
            dict: 包含所有路径的字典
                - identity: 身份文件路径
                - info: 信息文件路径
                - key: 密钥文件路径
        """
        return {
            'identity': cls.get_identity_path(folder_path),
            'info': cls.get_info_path(folder_path),
            'key': cls.get_key_path(folder_path)
        }
