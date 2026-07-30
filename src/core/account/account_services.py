"""账户文件夹操作与异常恢复."""

import os
from pathlib import Path
from typing import Optional

from src.core.config import ConfigService
from src.core.constants import KEY_FOLDER, TAG_FILE, TDATA_DIR
from src.core.logger import Logger
from src.core.runtime import generate_temp_name


def find_account_folder(base_path_str: str, tag_name: str) -> Optional[str]:
    """遍历 Telegram 目录，寻找含有匹配 tas_tag 标签文件的文件夹（跳过软链接）."""
    try:
        base_dir = Path(base_path_str)
        if not base_dir.is_dir():
            return None

        for entry in base_dir.iterdir():
            if entry.is_symlink():
                continue
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


def is_tdata_link(base_path_str: str) -> bool:
    """检查 tdata 是否为软链接."""
    tdata_path = Path(base_path_str) / TDATA_DIR
    return tdata_path.is_symlink()


def get_tdata_link_target(base_path_str: str) -> Optional[str]:
    """获取 tdata 软链接指向的目标文件夹名."""
    tdata_path = Path(base_path_str) / TDATA_DIR
    if tdata_path.is_symlink():
        try:
            return Path(os.readlink(str(tdata_path))).name
        except OSError:
            return None
    return None


def remove_tdata_link(base_path_str: str) -> bool:
    """移除 tdata 软链接（不影响目标目录）."""
    tdata_path = Path(base_path_str) / TDATA_DIR
    if tdata_path.is_symlink():
        try:
            os.unlink(str(tdata_path))
            return True
        except OSError:
            return False
    return True


def _migrate_real_tdata(base_path_str: str) -> Optional[str]:
    """将实体 tdata 目录迁移为账户目录，返回迁移后的文件夹名."""
    base_path = Path(base_path_str)
    tdata_path = base_path / TDATA_DIR

    if not tdata_path.exists() or tdata_path.is_symlink():
        return None

    tas_tag_file = tdata_path / TAG_FILE
    tag_name = None
    if tas_tag_file.exists():
        try:
            tag_name = tas_tag_file.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            pass

    if tag_name:
        target_folder = f"{TDATA_DIR}-{tag_name}"
    else:
        target_folder = generate_temp_name()

    target_path = base_path / target_folder
    if target_path.exists():
        return None

    try:
        tdata_path.rename(target_path)
        return target_folder
    except OSError:
        return None


def repoint_tdata_link(base_path_str: str, target_folder_name: str) -> bool:
    """重指向 tdata 软链接到目标账户目录（覆盖原有链接）."""
    base_path = Path(base_path_str)
    tdata_path = base_path / TDATA_DIR
    target_path = base_path / target_folder_name

    if not target_path.is_dir():
        return False

    if tdata_path.is_symlink():
        current_target = get_tdata_link_target(base_path_str)
        if current_target == target_folder_name:
            return True
        try:
            os.unlink(str(tdata_path))
        except OSError:
            return False
    elif tdata_path.exists():
        migrated = _migrate_real_tdata(base_path_str)
        if not migrated:
            return False
    else:
        pass

    try:
        os.symlink(target_folder_name, str(tdata_path), target_is_directory=True)
        return True
    except OSError:
        return False


def get_key_datas_path(folder_path: Path) -> Path:
    """获取指定文件夹下 key_datas 文件的完整路径."""
    return folder_path / KEY_FOLDER


class AccountRecoveryService:
    """账户恢复服务."""

    def __init__(self, logger: Logger) -> None:
        """初始化账户恢复服务."""
        self.logger = logger

    def cleanup_orphan_folders(self, base_path_str: str, config_service: Optional[ConfigService] = None) -> None:
        """清理失效的 tdata 软链接，并处理遗留的实体 tdata 目录."""
        if not base_path_str:
            return

        base_path = Path(base_path_str)
        if not base_path.is_dir():
            return

        tdata_path = base_path / TDATA_DIR

        if tdata_path.is_symlink() and not tdata_path.exists():
            try:
                os.unlink(str(tdata_path))
                self.logger.warning("检测到失效的 tdata 软链接，已移除")
            except OSError as e:
                self.logger.warning(f"移除失效 tdata 软链接失败: {e}")

        if tdata_path.exists() and not tdata_path.is_symlink():
            migrated = _migrate_real_tdata(base_path_str)
            if migrated:
                try:
                    os.symlink(migrated, str(tdata_path), target_is_directory=True)
                    self.logger.warning(f"已将实体 tdata 迁移为软链接 -> {migrated}")
                except OSError as e:
                    self.logger.warning(f"创建 tdata 软链接失败: {e}")

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
