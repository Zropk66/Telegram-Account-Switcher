"""账户运行监控."""

import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import psutil
from watchdog.events import FileMovedEvent, FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.core.account.account_operations import restore_default
from src.core.config import ConfigService
from src.core.constants import (
    MONITOR_MTIME_CHECK_INTERVAL,
    MONITOR_SESSION_MIN_DURATION,
    TDATA_DIR,
    TELEGRAM_CONFIGS_SUBPATH,
    TELEGRAM_IDENTITY_KEY,
)
from src.core.logger import Logger


class _ConfigsFileHandler(FileSystemEventHandler):
    """监控配置文件变化."""

    def __init__(self, target_file: Path, wake_event: threading.Event, login_flag: list) -> None:
        """初始化配置文件事件处理器."""
        super().__init__()
        self._target_name = target_file.name
        self._wake_event = wake_event
        self._login_flag = login_flag

    def _match(self, event: FileSystemEvent) -> bool:
        """检查事件是否匹配目标配置文件."""
        if event.is_directory:
            return False
        try:
            return Path(event.src_path).name == self._target_name
        except (ValueError, OSError):
            return False

    def _on_file_event(self, event: FileSystemEvent) -> None:
        """处理匹配的文件事件."""
        if self._match(event):
            self._login_flag[0] = True
            self._wake_event.set()

    def on_modified(self, event: FileSystemEvent) -> None:
        """文件修改事件回调."""
        self._on_file_event(event)

    def on_created(self, event: FileSystemEvent) -> None:
        """文件创建事件回调."""
        self._on_file_event(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        """文件删除事件回调."""
        self._on_file_event(event)

    def on_moved(self, event: FileMovedEvent) -> None:
        """文件重命名或移动事件回调."""
        if not event.is_directory:
            try:
                if Path(event.dest_path).name == self._target_name:
                    self._login_flag[0] = True
                    self._wake_event.set()
            except (ValueError, OSError):
                pass


class AccountMonitor:
    """账户退出与登录监控器."""

    _MTIME_CHECK_INTERVAL = MONITOR_MTIME_CHECK_INTERVAL

    def __init__(
        self,
        tag: str,
        check_tag: str | None,
        config_manage: ConfigService,
        logger: Logger,
        spawn_time: datetime | None = None,
        target_folder: str | None = None,
    ) -> None:
        """初始化账户监控器."""
        self.tag = tag
        self.check_tag = check_tag
        self.config = config_manage
        self.logger = logger
        self.spawn_time = spawn_time or datetime.now()
        self.target_folder = target_folder
        folder_name = target_folder or TDATA_DIR
        self.configs_file = Path(config_manage.path) / folder_name / TELEGRAM_IDENTITY_KEY / TELEGRAM_CONFIGS_SUBPATH

        self._wake_event = threading.Event()
        self.completion_event = threading.Event()
        self._process_alive = True
        self._login_detected = [False]
        self._observer: Observer | None = None
        self._login_callbacks: list[Callable[[str], None]] = []
        self._completion_callbacks: list[Callable[[bool, str], None]] = []

    def register_on_login(self, callback: Callable[[str], None]) -> None:
        """注册登录成功回调."""
        if callback not in self._login_callbacks:
            self._login_callbacks.append(callback)

    def register_on_completion(self, callback: Callable[[bool, str], None]) -> None:
        """注册监控完成回调."""
        if callback not in self._completion_callbacks:
            self._completion_callbacks.append(callback)

    def handle_process_status(self, is_alive: bool, pid: Optional[int] = None) -> None:
        """处理进程存活状态变更."""
        self._process_alive = is_alive
        self._wake_event.set()

    def _check_mtime(self) -> bool:
        """通过修改时间辅助检测登录状态."""
        try:
            if self.configs_file.exists():
                return self.configs_file.stat().st_mtime >= self.spawn_time.timestamp()
        except OSError:
            pass
        return False

    def run(self) -> None:
        """运行监控主线程."""
        is_logged_in = False
        monitor_started = False

        try:
            self._process_alive = any(p.info["name"] == self.config.client for p in psutil.process_iter(["name"]))
        except Exception as e:
            self.logger.warning(f"初始化检查进程存活状态时发生异常: {e}")
            self._process_alive = True
        if not self._process_alive:
            self._wake_event.set()

        configs_dir = self.configs_file.parent
        if configs_dir.exists():
            handler = _ConfigsFileHandler(self.configs_file, self._wake_event, self._login_detected)
            self._observer = Observer()
            self._observer.schedule(handler, str(configs_dir))
            self._observer.start()

        self.logger.debug(f"监控已启动：{self.tag or self.config.default}")
        try:
            while True:
                self._wake_event.wait(timeout=self._MTIME_CHECK_INTERVAL)
                self._wake_event.clear()

                if self._process_alive:
                    if not is_logged_in:
                        if not self._login_detected[0]:
                            self._login_detected[0] = self._check_mtime()

                        if self._login_detected[0]:
                            self.logger.info("检测到登录成功")
                            is_logged_in = True
                            self.config.start_time = datetime.now()
                            monitor_started = True
                            for cb in list(self._login_callbacks):
                                try:
                                    cb(self.tag or self.config.default)
                                except Exception as e:
                                    self.logger.exception("登录回调执行失败", e)
                else:
                    if not is_logged_in:
                        self.logger.warning("检测到 Telegram 在登录成功前意外关闭")

                    if self.tag and self.tag != self.config.default:
                        if monitor_started:
                            running_time = datetime.now() - self.config.start_time
                            if running_time.total_seconds() >= MONITOR_SESSION_MIN_DURATION and is_logged_in:
                                self.logger.info(f"正在备份账户密钥：{self.tag}")
                                account_dir = Path(self.config.path) / (self.target_folder or TDATA_DIR)
                                self.config.backup_account_keys(self.tag, account_dir)

                        self.logger.debug("正在恢复默认账户状态...")
                        restore_default()
                    break
        except Exception as e:
            self.logger.exception("监控线程发生未捕获异常", e)
        finally:
            self.logger.debug("正在清理资源...")
            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=2)
            self.config.sync_all_account_paths()

            for cb in list(self._completion_callbacks):
                try:
                    cb(True, "会话已正常结束")
                except Exception as e:
                    self.logger.exception("完成回调执行失败", e)
            self.completion_event.set()
