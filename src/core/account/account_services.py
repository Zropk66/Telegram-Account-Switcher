"""账户文件夹操作与异常恢复."""

from pathlib import Path
from typing import Optional

from src.core.config import ConfigService
from src.core.constants import KEY_FOLDER, TAG_FILE, TDATA_DIR
from src.core.logger import Logger
from src.core.utils import safe_rename


def find_account_folder(base_path_str: str, tag_name: str) -> Optional[str]:
    """遍历 Telegram 目录，寻找含有匹配 tas_tag 标签文件的文件夹."""
    try:
        base_dir = Path(base_path_str)
        if not base_dir.is_dir():
            return None

        for entry in base_dir.iterdir():
            if entry.is_dir():
                tas_tag_file = entry / TAG_FILE
                if tas_tag_file.exists():
                    try:
                        content = tas_tag_file.read_bytes()
                        if content.decode("utf-8").strip() == tag_name:
                            return entry.name
                    except (OSError, UnicodeDecodeError) as e:
                        Logger().warning(f"读取或解析目录 {entry.name} 中的 {TAG_FILE} 失败: {e}")
        return None
    except OSError as e:
        Logger().error(f"遍历账户根目录失败: {e}")
        return None


def swap_active_tdata_with_target(base_path_str: str, target_folder_name: str, temp_prefix: str) -> bool:
    """原子化地交换活跃 tdata 与目标账户目录."""
    base_path = Path(base_path_str)
    tdata_path = base_path / TDATA_DIR
    temp_path = base_path / temp_prefix
    target_path = base_path / target_folder_name

    if target_path == tdata_path:
        return True

    try:
        with safe_rename(tdata_path, temp_path):
            target_path.rename(tdata_path)
        return True
    except (FileNotFoundError, PermissionError, OSError):
        return False


def get_key_datas_path(folder_path: Path) -> Path:
    """获取指定文件夹下 key_datas 文件的完整路径."""
    return folder_path / KEY_FOLDER


class AccountRecoveryService:
    """账户恢复服务."""

    def __init__(self, logger: Logger) -> None:
        """初始化账户恢复服务."""
        self.logger = logger

    def cleanup_orphan_folders(self, base_path_str: str) -> None:
        """清理异常中断遗留的临时文件夹."""
        if not base_path_str:
            return

        base_path = Path(base_path_str)
        if not base_path.is_dir():
            return

        tdata_path = Path(base_path_str) / TDATA_DIR
        if not tdata_path.exists():
            for entry in Path(base_path_str).iterdir():
                if entry.name.startswith(f"{TDATA_DIR}-") and entry.is_dir():
                    try:
                        self.logger.warning(f"检测到异常中断，正在从 {entry.name} 恢复...")
                        entry.rename(tdata_path)
                        return
                    except OSError as rename_err:
                        self.logger.warning(f"从临时目录 {entry.name} 恢复 {TDATA_DIR} 失败: {rename_err}")
                        continue

    def recover_account(self, tag: str, config_manage: ConfigService) -> bool:
        """从备份密钥还原损坏的账户."""
        self.logger.warning(f"检测到账户 '{tag}' 可能损坏，执行恢复...")
        target_account = config_manage.get_account(tag)
        if target_account and target_account.get("folder"):
            target_path = Path(config_manage.path) / target_account["folder"]
            recovered = config_manage.login_with_keys(tag, str(target_path))
            if recovered:
                self.logger.info(f"账户 '{tag}' 密钥恢复完成，请重启客户端")
                return True
        return False
