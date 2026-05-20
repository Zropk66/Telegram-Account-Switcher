"""
Telegram 数据目录结构定义。

该模块维护了 Telegram tdata 内部的文件布局常量。
注意：这里的十六进制字符串（如 D877F783D5D3EF8C）是 Telegram 内部硬编码的
特定版本/类型的标识符，修改会导致账户无法被识别。
"""

from pathlib import Path


class PathConfig:
    """tdata 关键路径映射。"""

    IDENTITY_FOLDER = 'D877F783D5D3EF8Cs'
    INFO_SUBFOLDER = 'maps'
    KEY_FOLDER = 'key_datas'
    CONFIG_FILE = "configs.json"

    @classmethod
    def get_identity_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """定位 identity 文件路径。"""
        path = folder_path / cls.IDENTITY_FOLDER
        if auto_create:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_info_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """定位 info/maps (账户元数据) 路径。"""
        path = folder_path / 'D877F783D5D3EF8C' / cls.INFO_SUBFOLDER
        if auto_create:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_key_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """定位关键密钥文件路径。"""
        path = folder_path / cls.KEY_FOLDER
        if auto_create:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_all_paths(cls, folder_path: Path) -> dict:
        """汇总获取 tdata 目录下的三个核心路径。"""
        return {
            'identity': cls.get_identity_path(folder_path),
            'info': cls.get_info_path(folder_path),
            'key': cls.get_key_path(folder_path)
        }
