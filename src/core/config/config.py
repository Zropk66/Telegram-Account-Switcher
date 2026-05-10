"""
路径常量与工具方法

存放 Telegram tdata 目录下各子文件夹的名称，
以及根据基础路径拼接出完整目录的方法。
"""

from pathlib import Path


class PathConfig:
    """Telegram tdata 目录结构定义"""

    # tdata 下的文件夹名（Telegram 内部命名，不要随意改动）
    IDENTITY_FOLDER = 'D877F783D5D3EF8Cs'
    INFO_SUBFOLDER = 'maps'
    KEY_FOLDER = 'key_datas'

    @classmethod
    def get_identity_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """返回 identity 文件夹路径，需要时自动创建目录"""
        path = folder_path / cls.IDENTITY_FOLDER
        if auto_create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_info_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """返回 info/maps 文件夹路径，需要时自动创建目录"""
        path = folder_path / 'D877F783D5D3EF8C' / cls.INFO_SUBFOLDER
        if auto_create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_key_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """返回 key_datas 文件夹路径，需要时自动创建目录"""
        path = folder_path / cls.KEY_FOLDER
        if auto_create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_all_paths(cls, folder_path: Path) -> dict:
        """一次性获取 identity / info / key 三个子路径"""
        return {
            'identity': cls.get_identity_path(folder_path),
            'info': cls.get_info_path(folder_path),
            'key': cls.get_key_path(folder_path)
        }
