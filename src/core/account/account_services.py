"""
账户文件系统管理与异常恢复服务。
"""

import contextlib
from pathlib import Path
from typing import Optional

from src.core.interfaces import ILogger, IConfigProvider, IAccountRecoveryService


def find_account_folder(base_path_str: str, tag_name: str) -> Optional[str]:
    """依据标签文件 `tas_tag` 定位账户对应文件夹。"""
    try:
        base_dir = Path(base_path_str)
        if not base_dir.is_dir():
            return None

        for entry in base_dir.iterdir():
            if entry.is_dir():
                tas_tag_file = entry / "tas_tag"
                if tas_tag_file.exists():
                    try:
                        content = tas_tag_file.read_bytes()
                        if content.decode("utf-8").strip() == tag_name:
                            return entry.name
                    except (OSError, UnicodeDecodeError):
                        pass
        return None
    except OSError:
        return None


def swap_active_tdata_with_target(base_path_str: str, target_folder_name: str, temp_prefix: str) -> bool:
    """以原子方式交换当前活跃的 `tdata` 与目标账户文件夹。"""
    base_path = Path(base_path_str)
    tdata_path = base_path / "tdata"
    temp_path = base_path / temp_prefix
    target_path = base_path / target_folder_name

    if target_path == tdata_path:
        return True

    try:
        with _atomic_rename(tdata_path, temp_path):
            target_path.rename(tdata_path)
        return True
    except (FileNotFoundError, PermissionError, OSError):
        return False


@contextlib.contextmanager
def _atomic_rename(src: Path, dst: Path):
    """提供临时目录中转的安全重命名上下文。"""
    if not src.exists():
        yield
        return

    src.rename(dst)
    try:
        yield
    except Exception:
        if dst.exists() and not src.exists():
            with contextlib.suppress(Exception):
                dst.rename(src)
        raise


def get_key_datas_path(folder_path: Path) -> Path:
    """获取账户加密数据文件的路径。"""
    return folder_path / "key_datas"


class AccountRecoveryService(IAccountRecoveryService):
    """处理异常切换场景，包括遗留文件夹清理与备份密钥的重建。"""

    def __init__(self, logger: ILogger):
        """初始化。"""
        self.logger = logger

    def cleanup_orphan_folders(self, base_path_str: str):
        """若上次切换因进程崩溃未完成，尝试从临时目录恢复到 `tdata`。"""
        if not base_path_str:
            return

        base_path = Path(base_path_str)
        if not base_path.is_dir():
            return

        tdata_path = base_path / "tdata"
        if not tdata_path.exists():
            for entry in base_path.iterdir():
                if entry.name.startswith("tdata-") and entry.is_dir():
                    try:
                        self.logger.warning(f"检测到异常中断，正在从 {entry.name} 恢复...")
                        entry.rename(tdata_path)
                        return
                    except OSError:
                        continue

    def recover_account(self, tag: str, config_manage: IConfigProvider) -> bool:
        """尝试使用备份密钥重新构建损坏的账户数据。"""
        self.logger.warning(f"检测到账户 '{tag}' 可能损坏，执行恢复...")
        target_account = config_manage.get_account(tag)
        if target_account and target_account.get('folder'):
            target_path = Path(config_manage.path) / target_account['folder']
            recovered = config_manage.login_with_keys(tag, str(target_path))
            if recovered:
                self.logger.info(f"账户 '{tag}' 密钥恢复完成，请重启客户端")
                return True
        return False
