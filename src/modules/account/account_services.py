# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional

from src.modules.logger import Logger
from src.modules.utils import search_file_in_dirs, atomic_rename


class AccountFileSystemService:
    """账户文件系统操作"""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)

    def find_account_folder(self, tag: str) -> Optional[str]:
        """查找标签对应的文件夹"""
        return search_file_in_dirs(str(self.base_path), tag)

    def swap_active_tdata_with_target(self, target_folder_name: str, temp_prefix: str) -> bool:
        """安全交换当前 tdata 文件夹与目标文件夹"""
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
    """账户恢复处理"""

    def __init__(self, logger: Logger):
        self.logger = logger

    def cleanup_orphan_folders(self, base_path_str: str):
        """检查并恢复异常中断时的文件夹"""
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
        """使用备份密钥恢复账户"""
        self.logger.warning(f"检测到账户 '{tag}' 可能损坏，执行恢复...")
        target_account = config_manage.get_account(tag)
        if target_account and target_account.get('folder'):
            target_path = Path(config_manage.path) / target_account['folder']
            recovered = config_manage.login_with_keys(tag, str(target_path))
            if recovered:
                self.logger.info(f"账户 '{tag}' 密钥恢复完成，请重启客户端")
                return True
        return False
