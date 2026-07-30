"""账户切换协调."""

from contextlib import contextmanager
from datetime import datetime
from typing import Callable, Generator, Optional, Tuple

from src.core.account.account_monitor import AccountMonitor
from src.core.account.account_operations import restore_default, switch_to_tag
from src.core.account.account_services import AccountRecoveryService
from src.core.config import ConfigService
from src.core.constants import LaunchMode
from src.core.logger import Logger
from src.core.process_manager import ProcessManager


class AccountSwitcher:
    """账户切换协调器."""

    def __init__(self) -> None:
        """初始化账户切换协调器."""
        self._config = ConfigService()
        self.logger = Logger()
        self._process_manager = ProcessManager()
        self._recovery_service = AccountRecoveryService(self.logger)
        self.monitor: Optional[AccountMonitor] = None

    @contextmanager
    def switching_session(self, actual_default_folder: Optional[str] = None) -> Generator[None, None, None]:
        """管理切换会话."""
        self._recovery_service.cleanup_orphan_folders(self._config.path)
        with self._process_manager.kill_and_guard(self._config.client):
            try:
                yield
            except Exception as e:
                self.logger.error(f"账户切换过程中出现异常: {e}")
                self._rollback_to_default(actual_default_folder)
                raise

    def process(self, confirm_callback: Optional[Callable[[str], bool]] = None) -> bool:
        """执行账户切换流程."""
        tag = self._config.tag
        default_tag = self._config.default

        target_folder = self._config.get_account(tag).get("folder")
        default_folder = self._config.get_account(default_tag).get("folder")

        from src.core.account.account_services import find_account_folder

        if tag and not target_folder:
            target_folder = find_account_folder(self._config.path, tag)
        if default_tag and not default_folder:
            default_folder = find_account_folder(self._config.path, default_tag)

        check_tag = None
        needs_recovery = False
        spawn_time = None
        success = False
        should_monitor = False

        try:
            with self.switching_session(actual_default_folder=default_folder):
                success, should_monitor, spawn_time = self._process(
                    confirm_callback, target_folder, default_folder
                )
                if success:
                    check_tag = tag or self._config.default
                    if not should_monitor:
                        self._config.sync_all_account_paths()
                        return True
                else:
                    if self._config.has_complete_keys(tag):
                        self.logger.warning(f"账户 '{tag}' 启动失败，标记为损坏并尝试密钥恢复")
                        needs_recovery = True
                    self._rollback_to_default(default_folder)
        except Exception as e:
            self.logger.exception("账户切换流程发生严重错误", e)
            self._config.sync_all_account_paths()
            return False

        if success:
            if should_monitor:
                active_folder = target_folder if (tag and tag != self._config.default) else default_folder
                self.monitor = AccountMonitor(
                    tag,
                    check_tag,
                    self._config,
                    self.logger,
                    spawn_time=spawn_time,
                    target_folder=active_folder if self._config.launch_mode == LaunchMode.HOOK else None,
                )
            self._config.sync_all_account_paths()
            return True

        if needs_recovery:
            self._recovery_service.recover_account(tag, self._config)
            self._config.sync_all_account_paths()
            return False

        self._config.sync_all_account_paths()
        return False

    def _rollback_to_default(self, actual_default_folder: Optional[str] = None) -> None:
        """回滚还原到默认账户（软链接模式下仅需重指向，无需数据移动）."""
        try:
            restore_default(target_folder=actual_default_folder)
        except Exception as restore_err:
            self.logger.error(f"回滚中还原默认账户失败: {restore_err}")
            raise

    def _fallback_to_symlink(
        self,
        is_default: bool,
        confirm_callback: Optional[Callable[[str], bool]],
        target_folder: Optional[str],
        default_folder: Optional[str],
    ) -> bool:
        """hook 模式启动失败后降级为链接模式."""
        self.logger.warning("hook 模式启动失败，降级为链接模式")

        # 清理可能残留的进程（hook 注入失败可能留下半启动的进程）
        try:
            self._process_manager.kill_process(self._config.client)
        except Exception as e:
            self.logger.warning(f"降级时清理残留进程失败: {e}")

        # 补做软链接操作
        if is_default:
            if not restore_default(target_folder=default_folder):
                self.logger.error("降级失败：无法还原默认账户软链接")
                return False
        else:
            if not switch_to_tag(confirm_callback=confirm_callback, target_folder=target_folder):
                self.logger.error("降级失败：无法重指向软链接")
                return False

        # 用链接模式启动
        return self._process_manager.start_process(wait=True, force_symlink=True)

    def _process(
        self,
        confirm_callback: Optional[Callable[[str], bool]] = None,
        target_folder: Optional[str] = None,
        default_folder: Optional[str] = None,
    ) -> Tuple[bool, bool, datetime]:
        """执行账户切换和启动流程."""
        tag = self._config.tag
        tags = self._config.tags
        is_hook = self._config.launch_mode == LaunchMode.HOOK

        if tag not in tags or tag == self._config.default:
            self.logger.debug(f"切换目标为默认账户: {self._config.default}")
            if not is_hook:
                success = restore_default(target_folder=default_folder)
            else:
                success = True
            spawn_time = datetime.now()
            if success:
                success = self._process_manager.start_process(wait=True, tdata_name=default_folder)
                if not success and is_hook and self._config.hook_fallback:
                    success = self._fallback_to_symlink(
                        is_default=True,
                        confirm_callback=confirm_callback,
                        target_folder=target_folder,
                        default_folder=default_folder,
                    )
            return success, True, spawn_time

        self.logger.debug(f"正在准备切换到账户: {tag}")
        if is_hook:
            self.logger.debug("使用 hook 模式启动进程")
            spawn_time = datetime.now()
            success = self._process_manager.start_process(wait=True, tdata_name=target_folder)
            if not success and self._config.hook_fallback:
                success = self._fallback_to_symlink(
                    is_default=False,
                    confirm_callback=confirm_callback,
                    target_folder=target_folder,
                    default_folder=default_folder,
                )
            if success:
                self.logger.info(f"账户 '{tag}' 启动成功")
            else:
                self.logger.error(f"账户 '{tag}' 启动失败（可能是数据损坏或权限问题）")
            return success, True, spawn_time

        if switch_to_tag(confirm_callback=confirm_callback, target_folder=target_folder):
            self.logger.debug("软链接重指向完成，正在启动进程")
            spawn_time = datetime.now()
            success = self._process_manager.start_process(wait=True)
            if success:
                self.logger.info(f"账户 '{tag}' 启动成功")
            else:
                self.logger.error(f"账户 '{tag}' 启动失败（可能是数据损坏或权限问题）")
            return success, True, spawn_time
        else:
            self.logger.error("账户切换失败：无法重指向软链接，请检查是否有文件被占用")
            return False, False, datetime.now()
