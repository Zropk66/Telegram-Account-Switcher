"""配置路径管理器."""

from pathlib import Path

from src.core.constants import CONFIG_FILE, IDENTITY_FOLDER, INFO_SUBFOLDER, KEY_FOLDER, TELEGRAM_IDENTITY_KEY


class PathConfig:
    """配置路径管理器."""

    IDENTITY_FOLDER = IDENTITY_FOLDER
    INFO_SUBFOLDER = INFO_SUBFOLDER
    KEY_FOLDER = KEY_FOLDER
    CONFIG_FILE = CONFIG_FILE

    @classmethod
    def get_identity_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """获取身份凭证文件路径."""
        path = folder_path / cls.IDENTITY_FOLDER
        if auto_create:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_info_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """获取配置信息文件路径."""
        path = folder_path / TELEGRAM_IDENTITY_KEY / cls.INFO_SUBFOLDER
        if auto_create:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_key_path(cls, folder_path: Path, auto_create: bool = False) -> Path:
        """获取核心密钥文件路径."""
        path = folder_path / cls.KEY_FOLDER
        if auto_create:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_all_paths(cls, folder_path: Path) -> dict:
        """获取所有核心密钥和数据文件路径."""
        return {
            "identity": cls.get_identity_path(folder_path),
            "info": cls.get_info_path(folder_path),
            "key": cls.get_key_path(folder_path),
        }
