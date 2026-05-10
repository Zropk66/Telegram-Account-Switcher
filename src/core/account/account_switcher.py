import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Tuple

from src.core.account.account_monitor import AccountMonitor
from src.core.account.account_operations import restore_default, switch_to_tag
from src.core.account.account_services import AccountRecoveryService
from src.core.config import ConfigService
from src.core.logger import Logger
from src.core.process_manager import ProcessManager
from src.core.utils import is_exists


class AccountSwitcher:
    """协调账户切换的完整流程：加锁、切换、监控、异常恢复。"""

    def __init__(self):
        self.logger = Logger()
        self._config = ConfigService()
        self._process_manager = ProcessManager()
        self._recovery_service = AccountRecoveryService(self.logger)

    @contextmanager
    def switching_session(self) -> Generator[None, None, None]:
        """切换会话上下文，确保异常时能回滚到默认账户。"""
        self._recovery_service.cleanup_orphan_folders(self._config.path)

        with self._process_manager.locked(self._config.client):
            try:
                yield
            except Exception as e:
                self.logger.error(f"切换过程中发生错误，尝试恢复默认状态: {e}")
                restore_default()
                raise

    def process(self, confirm_callback=None):
        """执行完整的账户切换流程，返回切换是否成功。"""
        tag = self._config.tag
        check_tag = None
        needs_recovery = False
        spawn_time = None

        with self.switching_session():
            try:
                success, should_monitor, spawn_time = self._process(confirm_callback)
                if not success:
                    self.logger.error("客户端启动失败.")
                    if self._config.has_complete_keys(tag):
                        needs_recovery = True
                    else:
                        return False

                if success:
                    check_tag = tag or self._config.default
                    if is_exists(str(Path(self._config.path) / "tdata"), check_tag):
                        self.logger.info(f"客户端启动成功 -> '{check_tag}'")

                    if not should_monitor:
                        return True
            except Exception as e:
                self.logger.exception("执行切换流程时发生异常", e)
                return False

        if success:
            if should_monitor:
                monitor = AccountMonitor(tag, check_tag, self._config, self.logger, spawn_time=spawn_time)
                threading.Thread(target=monitor.run, daemon=True).start()
            self._config.sync_all_account_paths()
            return True

        if needs_recovery:
            self._recovery_service.recover_account(tag, self._config)
            self._config.sync_all_account_paths()
            return False

        self._config.sync_all_account_paths()
        return False

    def _process(self, confirm_callback=None) -> Tuple[bool, bool, datetime]:
        """执行实际的切换逻辑，返回 (是否成功, 是否需要启动监控, 进程启动时间)。"""
        tag = self._config.tag
        tags = self._config.tags

        # 没有指定 tag 或者 tag 就是默认账户，直接还原
        if tag not in tags or tag == self._config.default:
            restore_default()
            spawn_time = datetime.now()
            success = self._process_manager.start_process(wait=True)
            return success, True, spawn_time

        if switch_to_tag(confirm_callback=confirm_callback):
            self.logger.info(f"已切换为目标账户 -> '{tag}'.")
            spawn_time = datetime.now()
            success = self._process_manager.start_process(wait=True)
            return success, True, spawn_time
        else:
            self.logger.error(f"交换文件失败，无法切换到 '{tag}'.")
            return False, False, datetime.now()
