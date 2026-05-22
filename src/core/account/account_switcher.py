"""
账户切换协调。
"""

from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Tuple

from src.core.account.account_monitor import AccountMonitor
from src.core.account.account_operations import restore_default, switch_to_tag
from src.core.account.account_services import AccountRecoveryService
from src.core.config import ConfigService
from src.core.constants import TDATA_DIR
from src.core.logger import Logger
from src.core.process_manager import ProcessManager


class AccountSwitcher:
    """账户切换协调器。"""

    def __init__(self):
        """初始化账户切换协调器。"""
        self._config = ConfigService()
        self.logger = Logger()
        self._process_manager = ProcessManager()
        self._recovery_service = AccountRecoveryService(self.logger)
        self.monitor: Optional[AccountMonitor] = None

    @contextmanager
    def switching_session(self, actual_default_folder: Optional[str] = None):
        """管理切换会话。"""
        self._recovery_service.cleanup_orphan_folders(self._config.path)
        with self._process_manager.kill_and_guard(self._config.client):
            try:
                yield
            except Exception as e:
                self.logger.error(f"账户切换过程中出现异常: {e}")
                self._rollback_to_default(actual_default_folder)
                raise

    def process(self, confirm_callback=None) -> bool:
        """执行账户切换流程。"""
        tag = self._config.tag
        default_tag = self._config.default

        target_folder = self._config.get_account(tag).get('folder')
        default_folder = self._config.get_account(default_tag).get('folder')

        from src.core.account.account_services import find_account_folder
        if tag and not target_folder:
            target_folder = find_account_folder(self._config.path, tag)
        if default_tag and not default_folder:
            default_folder = find_account_folder(self._config.path, default_tag)

        from src.core.runtime import generate_temp_name
        temp_name = generate_temp_name()

        is_default_active = (not default_folder or default_folder == TDATA_DIR)
        actual_default_folder = temp_name if is_default_active else default_folder

        check_tag = None
        needs_recovery = False
        spawn_time = None
        success = False
        should_monitor = False

        try:
            with self.switching_session(actual_default_folder=actual_default_folder):
                success, should_monitor, spawn_time = self._process(confirm_callback, target_folder, default_folder,
                                                                    temp_name)
                if success:
                    check_tag = tag or self._config.default
                    if not should_monitor:
                        self._config.sync_all_account_paths()
                        return True
                else:
                    if self._config.has_complete_keys(tag):
                        self.logger.warning(f"账户 '{tag}' 启动失败，标记为损坏并尝试密钥恢复")
                        needs_recovery = True
                    self._rollback_to_default(actual_default_folder)
        except Exception as e:
            self.logger.exception("账户切换流程发生严重错误", e)
            self._config.sync_all_account_paths()
            return False

        if success:
            if should_monitor:
                self.monitor = AccountMonitor(tag, check_tag, self._config, self.logger, spawn_time=spawn_time)
            self._config.sync_all_account_paths()
            return True

        if needs_recovery:
            self._recovery_service.recover_account(tag, self._config)
            self._config.sync_all_account_paths()
            return False

        self._config.sync_all_account_paths()
        return False

    def _rollback_to_default(self, actual_default_folder: Optional[str] = None):
        """回滚还原到默认账户。"""
        from pathlib import Path

        tdata_path = Path(self._config.path) / TDATA_DIR
        actual_default_path = Path(self._config.path) / actual_default_folder if actual_default_folder else None

        should_backup_tdata = (
                actual_default_path
                and actual_default_path != tdata_path
                and actual_default_path.exists()
        )

        if should_backup_tdata:
            if tdata_path.exists():
                from src.core.runtime import generate_temp_name
                backup_name = generate_temp_name()
                for _ in range(5):
                    backup_path = Path(self._config.path) / backup_name
                    if not backup_path.exists():
                        break
                    backup_name = generate_temp_name()

                try:
                    tdata_path.rename(Path(self._config.path) / backup_name)
                    self.logger.warning(f"已将故障 tdata 重命名为 {backup_name}")
                except OSError as rename_err:
                    self.logger.error(f"回滚故障 tdata 失败: {rename_err}")

        target_folder_for_restore = None
        if should_backup_tdata:
            target_folder_for_restore = actual_default_folder
        elif actual_default_folder:
            target_folder_for_restore = TDATA_DIR

        try:
            restore_default(target_folder=target_folder_for_restore)
        except Exception as restore_err:
            self.logger.error(f"回滚中还原默认账户失败: {restore_err}")
            raise

    def _process(self, confirm_callback=None, target_folder: Optional[str] = None,
                 default_folder: Optional[str] = None, temp_name: Optional[str] = None) -> Tuple[bool, bool, datetime]:
        """执行账户切换和启动流程。"""
        tag = self._config.tag
        tags = self._config.tags

        if tag not in tags or tag == self._config.default:
            self.logger.debug(f"切换目标为默认账户: {self._config.default}")
            success = restore_default(target_folder=default_folder, temp_name=temp_name)
            spawn_time = datetime.now()
            if success:
                success = self._process_manager.start_process(wait=True)
            return success, True, spawn_time

        self.logger.debug(f"正在准备切换到账户: {tag}")
        if switch_to_tag(confirm_callback=confirm_callback, target_folder=target_folder, temp_name=temp_name):
            self.logger.debug(f"文件夹交换完成，正在启动进程")
            spawn_time = datetime.now()
            success = self._process_manager.start_process(wait=True)
            if success:
                self.logger.info(f"账户 '{tag}' 启动成功")
            else:
                self.logger.error(f"账户 '{tag}' 启动失败（可能是数据损坏或权限问题）")
            return success, True, spawn_time
        else:
            self.logger.error(f"账户切换失败：无法移动文件夹，请检查是否有文件被占用")
            return False, False, datetime.now()
