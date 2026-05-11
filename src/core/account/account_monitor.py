import threading
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.core.account.account_operations import restore_default
from src.core.event_bus import (
    Event,
    ProcessStatusChanged,
    AccountLoginDetected,
    AppCompletionEvent,
    get_event_bus,
    PROCESS_STATUS_CHANGED,
    ACCOUNT_LOGIN_DETECTED,
    APP_COMPLETION,
)
from src.core.logger import Logger


class _ConfigsFileHandler(FileSystemEventHandler):
    """用 watchdog 监听 configs 文件变化，作为登录检测的快速路径。

    当 configs 文件被修改/创建/删除/移动时，立即唤醒监控循环，
    避免纯轮询带来的延迟。
    """

    def __init__(self, target_file: Path, wake_event: threading.Event, login_flag: list):
        super().__init__()
        self._target_name = target_file.name
        self._wake_event = wake_event
        self._login_flag = login_flag

    def _match(self, event) -> bool:
        if event.is_directory:
            return False
        try:
            return Path(event.src_path).name == self._target_name
        except (ValueError, OSError):
            return False

    def _on_file_event(self, event):
        if self._match(event):
            self._login_flag[0] = True
            self._wake_event.set()

    def on_modified(self, event):
        self._on_file_event(event)

    def on_created(self, event):
        self._on_file_event(event)

    def on_deleted(self, event):
        self._on_file_event(event)

    def on_moved(self, event):
        if not event.is_directory:
            try:
                if Path(event.dest_path).name == self._target_name:
                    self._login_flag[0] = True
                    self._wake_event.set()
            except (ValueError, OSError):
                pass


class AccountMonitor:
    """后台监控线程，负责两件事：

    1. 检测登录：watchdog 监听 configs 文件（快速路径）+ mtime 兜底检查
    2. 监听进程退出：通过 EventBus 的 process.status_changed 事件驱动

    进程关闭后自动恢复默认账户，并根据使用时长决定是否同步密钥。
    """

    # mtime 兜底检查间隔（秒）
    _MTIME_CHECK_INTERVAL = 2.0

    def __init__(self, tag: str, check_tag: str | None, config_manage, logger: Logger, spawn_time: datetime | None = None):
        self.tag = tag
        self.check_tag = check_tag
        self.config = config_manage
        self.logger = logger
        self.spawn_time = spawn_time or datetime.now()
        self.configs_file = Path(config_manage.path) / "tdata" / "D877F783D5D3EF8C" / "configs"

        # 共享唤醒事件，watchdog 和 EventBus 都可以触发
        self._wake_event = threading.Event()
        # AccountMonitor 仅在进程启动成功后创建，初始状态必然是存活的
        self._process_alive = True
        self._login_detected = [False]
        self._observer: Observer | None = None

    def _check_mtime(self) -> bool:
        """兜底检查：直接看 configs 文件的 mtime 是否在进程启动之后被修改过。"""
        try:
            if self.configs_file.exists():
                return self.configs_file.stat().st_mtime >= self.spawn_time.timestamp()
        except OSError:
            pass
        return False

    def run(self):
        """事件驱动的主监控循环，在 daemon 线程中运行。"""
        is_logged_in = False
        monitor_started = False

        # -- 启动 watchdog 监听 configs 文件 --
        configs_dir = self.configs_file.parent
        if configs_dir.exists():
            handler = _ConfigsFileHandler(self.configs_file, self._wake_event, self._login_detected)
            self._observer = Observer()
            self._observer.schedule(handler, str(configs_dir))
            self._observer.start()

        # -- 订阅进程状态变化 --
        def on_process_status(payload: ProcessStatusChanged):
            self._process_alive = payload.is_alive
            self._wake_event.set()

        get_event_bus().subscribe(PROCESS_STATUS_CHANGED, on_process_status)

        try:
            while True:
                self._wake_event.wait(timeout=self._MTIME_CHECK_INTERVAL)
                self._wake_event.clear()

                if self._process_alive:
                    if not is_logged_in:
                        if not self._login_detected[0]:
                            # watchdog 没触发，用 mtime 兜底
                            self._login_detected[0] = self._check_mtime()

                        if self._login_detected[0]:
                            self.logger.info("账户登录成功")
                            is_logged_in = True
                            self.config.start_time = datetime.now()
                            monitor_started = True
                            get_event_bus().publish(Event(
                                ACCOUNT_LOGIN_DETECTED,
                                AccountLoginDetected(tag=self.tag or self.config.default),
                            ))
                else:
                    # 进程已关闭，清理并恢复默认账户
                    if self.tag and self.tag != self.config.default:
                        self.logger.info("正在恢复默认账户")

                        if monitor_started:
                            running_time = datetime.now() - self.config.start_time

                            # 使用超过 60 秒且已登录，认为本次使用有效，同步密钥
                            if running_time.total_seconds() >= 60 and is_logged_in:
                                self.logger.info(f"符合同步条件，更新密钥 -> '{self.tag}'")
                                self.config.backup_account_keys(self.tag, Path(self.config.path) / "tdata")

                        restore_default()
                    break
        except Exception as e:
            self.logger.exception("状态监控线程异常", e)
        finally:
            get_event_bus().unsubscribe(PROCESS_STATUS_CHANGED, on_process_status)
            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=2)
            self.config.sync_all_account_paths()
            get_event_bus().publish(Event(
                APP_COMPLETION,
                AppCompletionEvent(success=True, message="账户切换完成"),
            ))
