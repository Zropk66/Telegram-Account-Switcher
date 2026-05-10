from pathlib import Path
from typing import Optional

from src.core.logger import Logger
from src.core.utils import search_file_in_dirs, atomic_rename


class AccountFileSystemService:
    """封装账户数据目录的文件操作：查找文件夹、原子交换 tdata。"""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)

    def find_account_folder(self, tag: str) -> Optional[str]:
        """根据标签名在数据目录下查找对应的账户文件夹。"""
        return search_file_in_dirs(str(self.base_path), tag)

    def swap_active_tdata_with_target(self, target_folder_name: str, temp_prefix: str) -> bool:
        """原子交换活跃的 tdata 文件夹和目标文件夹，通过临时文件夹中转保证数据安全，返回是否成功。"""
        tdata_path = self.base_path / "tdata"
        temp_path = self.base_path / temp_prefix
        target_path = self.base_path / target_folder_name

        if target_path == tdata_path:
            return True

        try:
            with atomic_rename(tdata_path, temp_path):
                target_path.rename(tdata_path)
            return True
        except (FileNotFoundError, PermissionError, OSError):
            return False

    @staticmethod
    def get_key_datas_path(folder_path: Path) -> Path:
        return folder_path / "key_datas"


class AccountRecoveryService:
    """处理账户异常恢复：清理残留文件夹、用备份密钥重建账户。"""

    def __init__(self, logger: Logger):
        self.logger = logger

    def cleanup_orphan_folders(self, base_path_str: str):
        """检查上次切换是否异常中断，如果是则把临时文件夹恢复为 tdata。"""
        if not base_path_str:
            return

        base_path = Path(base_path_str)
        if not base_path.is_dir():
            return

        tdata_path = base_path / "tdata"
        if not tdata_path.exists():
            for entry in base_path.iterdir():
                if entry.is_dir() and entry.name.startswith("tdata-"):
                    try:
                        self.logger.warning(f"检测到异常中断，正在从 {entry.name} 恢复...")
                        entry.rename(tdata_path)
                        return
                    except OSError:
                        continue

    def recover_account(self, tag: str, config_manage):
        """用备份密钥重建损坏的账户数据，返回恢复是否成功。"""
        self.logger.warning(f"检测到账户 '{tag}' 可能损坏，执行恢复...")
        target_account = config_manage.get_account(tag)
        if target_account and target_account.get('folder'):
            target_path = Path(config_manage.path) / target_account['folder']
            recovered = config_manage.login_with_keys(tag, str(target_path))
            if recovered:
                self.logger.info(f"账户 '{tag}' 密钥恢复完成，请重启客户端")
                return True
        return False
