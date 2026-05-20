"""
账户切换协调器。

负责把进程控制、目录交换、失败回滚和后续监控串联成一次完整切换会话。
"""

import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Tuple

from src.core.account.account_monitor import AccountMonitor
from src.core.account.account_operations import restore_default, switch_to_tag
from src.core.account.account_services import AccountRecoveryService
from src.core.config import ConfigService
from src.core.logger import Logger
from src.core.process_manager import ProcessManager


class AccountSwitcher:
    """账户切换流程的业务编排层。"""

    def __init__(self):
        """初始化切换器，使用模块顶部的单例或直接实例化。"""
        self._config = ConfigService()
        self.logger = Logger()
        self._process_manager = ProcessManager()
        self._recovery_service = AccountRecoveryService(self.logger)

    @contextmanager
    def switching_session(self):
        """在切换期间关闭 Telegram，并在异常时尽量回滚到默认账户。"""
        self._recovery_service.cleanup_orphan_folders(self._config.path)
        with self._process_manager.kill_and_guard(self._config.client):
            try:
                yield
            except Exception as e:
                self.logger.error(f"账户切换过程中出现异常: {e}")
                restore_default()
                raise

    def process(self, confirm_callback=None) -> bool:
        """执行一次账户切换，并在成功后启动登录状态监控。"""
        tag = self._config.tag
        check_tag = None
        needs_recovery = False
        spawn_time = None

        with self.switching_session():
            try:
                success, should_monitor, spawn_time = self._process(confirm_callback)
                if success:
                    check_tag = tag or self._config.default
                    if not should_monitor:
                        self._config.sync_all_account_paths()
                        return True
                else:
                    if self._config.has_complete_keys(tag):
                        self.logger.warning(f"账户 '{tag}' 启动失败，标记为损坏并尝试密钥恢复")
                        needs_recovery = True
            except Exception as e:
                self.logger.exception("账户切换流程发生严重错误", e)
                self._config.sync_all_account_paths()
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
        """执行会话内的实际目录切换和客户端启动。"""
        tag = self._config.tag
        tags = self._config.tags

        if tag not in tags or tag == self._config.default:
            self.logger.debug(f"切换目标为默认账户: {self._config.default}")
            restore_default()
            spawn_time = datetime.now()
            success = self._process_manager.start_process(wait=True)
            return success, True, spawn_time

        self.logger.debug(f"正在准备切换到账户: {tag}")
        if switch_to_tag(confirm_callback=confirm_callback):
            self.logger.debug(f"文件夹交换完成，正在启动进程: {tag}")
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
