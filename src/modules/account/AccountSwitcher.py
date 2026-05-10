# -*- coding: utf-8 -*-
# @File ： AccountSwitcher.py
# @Time : 2025/8/5 23:45
# @Author : Zropk

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from src.modules.account.account_monitor import AccountMonitor
from src.modules.account.account_operations import restore_default, switch_to_tag
from src.modules.account.account_services import AccountRecoveryService
from src.modules.config_manager import ConfigManage
from src.modules.logger import Logger
from src.modules.process_manager import ProcessManager
from src.modules.utils import is_exists


class AccountSwitcher:
    """账户切换器 (Coordinator)"""

    def __init__(self):
        self.logger = Logger()
        self._config = ConfigManage()
        self._process_manager = ProcessManager()
        self._recovery_service = AccountRecoveryService(self.logger)

    @contextmanager
    def switching_session(self) -> Generator[None, None, None]:
        self._recovery_service.cleanup_orphan_folders(self._config.path)

        with self._process_manager.locked(self._config.client):
            try:
                yield
            except Exception as e:
                self.logger.error(f"切换过程中发生错误，尝试恢复默认状态: {e}")
                restore_default()
                raise

    def process(self, confirm_callback=None):
        """执行切换流程"""
        tag = self._config.tag
        check_tag = None
        needs_recovery = False

        with self.switching_session():
            try:
                success, should_monitor = self._process(confirm_callback)
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
                monitor = AccountMonitor(tag, check_tag, self._config, self.logger)
                threading.Thread(target=monitor.run, daemon=True).start()
            self._config.sync_all_account_paths()
            return True

        if needs_recovery:
            self._recovery_service.recover_account(tag, self._config)
            self._config.sync_all_account_paths()
            return False

        self._config.sync_all_account_paths()
        return False

    def _process(self, confirm_callback=None) -> tuple[bool, bool]:
        """切换逻辑执行"""
        tag = self._config.tag
        tags = self._config.tags

        if tag not in tags:
            restore_default()
            return self._process_manager.start_process(wait=True), True

        if switch_to_tag(confirm_callback=confirm_callback):
            self.logger.info(f"已切换为目标账户 -> '{tag}'.")
            return self._process_manager.start_process(wait=True), True
        else:
            self.logger.error(f"交换文件失败，无法切换到 '{tag}'.")
            return False, False
