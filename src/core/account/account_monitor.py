"""
后台监视 Telegram 运行状态，处理登录检测与进程生命周期管理。

通过监控文件系统事件和进程状态，在 Telegram 登录成功或退出时触发对应操作，
实现自动化的账户切换、密钥同步与现场恢复。
"""

import threading
from datetime import datetime
from pathlib import Path

import psutil
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.core.account.account_operations import restore_default
from src.core.config import ConfigService
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
    """
    监控 `configs` 文件的变动。

    Telegram 登录成功后会修改该文件，以此作为检测登录成功的非侵入式触发器。
    """

    def __init__(self, target_file: Path, wake_event: threading.Event, login_flag: list):
        """初始化。"""
        super().__init__()
        self._target_name = target_file.name
        self._wake_event = wake_event
        self._login_flag = login_flag

    def _match(self, event) -> bool:
        """判断文件事件是否针对目标配置文件。"""
        if event.is_directory:
            return False
        try:
            return Path(event.src_path).name == self._target_name
        except (ValueError, OSError):
            return False

    def _on_file_event(self, event):
        """内部方法：_on_file_event。"""
        if self._match(event):
            self._login_flag[0] = True
            # 唤醒等待中的监控线程
            self._wake_event.set()

    def on_modified(self, event):
        """on_modified 方法。"""
        self._on_file_event(event)

    def on_created(self, event):
        """on_created 方法。"""
        self._on_file_event(event)

    def on_deleted(self, event):
        """on_deleted 方法。"""
        self._on_file_event(event)

    def on_moved(self, event):
        """on_moved 方法。"""
        if not event.is_directory:
            try:
                if Path(event.dest_path).name == self._target_name:
                    self._login_flag[0] = True
                    self._wake_event.set()
            except (ValueError, OSError):
                pass


class AccountMonitor:
    """
    负责账户生命周期的后台监控逻辑。
    """

    # Watchdog 故障时的兜底轮询间隔
    _MTIME_CHECK_INTERVAL = 2.0

    def __init__(self, tag: str, check_tag: str | None, config_manage: ConfigService, logger: Logger,
                 spawn_time: datetime | None = None):
        """初始化。"""
        self.tag = tag
        self.check_tag = check_tag
        self.config = config_manage
        self.logger = logger
        self.spawn_time = spawn_time or datetime.now()
        # 定位 Telegram 内部存储配置的路径
        self.configs_file = Path(config_manage.path) / "tdata" / "D877F783D5D3EF8C" / "configs"

        self._wake_event = threading.Event()
        self._process_alive = True
        self._login_detected = [False]
        self._observer: Observer | None = None

    def _check_mtime(self) -> bool:
        """基于文件修改时间戳确认是否发生过登录（写入）。"""
        try:
            if self.configs_file.exists():
                return self.configs_file.stat().st_mtime >= self.spawn_time.timestamp()
        except OSError:
            pass
        return False

    def run(self):
        """
        核心监控主循环，运行于独立线程。
        """
        is_logged_in = False
        monitor_started = False

        # 初始化时检查进程存活状态，防止监控晚于进程启动而漏判
        try:
            self._process_alive = any(
                p.info['name'] == self.config.client
                for p in psutil.process_iter(['name'])
            )
        except Exception:
            self._process_alive = True
        if not self._process_alive:
            self._wake_event.set()

        # 启动文件系统监听
        configs_dir = self.configs_file.parent
        if configs_dir.exists():
            handler = _ConfigsFileHandler(self.configs_file, self._wake_event, self._login_detected)
            self._observer = Observer()
            self._observer.schedule(handler, str(configs_dir))
            self._observer.start()

        # 订阅进程状态变化事件
        def on_process_status(payload: ProcessStatusChanged):
            """on_process_status 方法。"""
            self._process_alive = payload.is_alive
            self._wake_event.set()

        get_event_bus().subscribe(PROCESS_STATUS_CHANGED, on_process_status)

        self.logger.debug(f"监控已启动：{self.tag or self.config.default}")
        try:
            while True:
                # 等待监控事件唤醒或轮询超时
                self._wake_event.wait(timeout=self._MTIME_CHECK_INTERVAL)
                self._wake_event.clear()

                if self._process_alive:
                    if not is_logged_in:
                        # 轮询二次确认登录
                        if not self._login_detected[0]:
                            self._login_detected[0] = self._check_mtime()

                        if self._login_detected[0]:
                            self.logger.info("检测到登录成功")
                            is_logged_in = True
                            self.config.start_time = datetime.now()
                            monitor_started = True
                            get_event_bus().publish(Event(
                                ACCOUNT_LOGIN_DETECTED,
                                AccountLoginDetected(tag=self.tag or self.config.default),
                            ))
                else:
                    # 进程退出后的清理与现场恢复
                    if not is_logged_in:
                        self.logger.error("检测到 Telegram 在登录成功前意外关闭")

                    # 若是非默认账户，需在退出后恢复默认环境
                    if self.tag and self.tag != self.config.default:
                        if monitor_started:
                            running_time = datetime.now() - self.config.start_time
                            # 仅对运行足够久（>60s）的会话进行变更备份，避免高频切换下的琐碎磁盘IO
                            if running_time.total_seconds() >= 60 and is_logged_in:
                                self.logger.info(f"正在备份账户密钥：{self.tag}")
                                self.config.backup_account_keys(self.tag, Path(self.config.path) / "tdata")

                        self.logger.debug(f"正在恢复默认账户状态...")
                        restore_default(config=self.config, logger=self.logger)
                    break
        except Exception as e:
            self.logger.exception("监控线程发生未捕获异常", e)
        finally:
            self.logger.debug("监控流程结束，正在清理资源...")
            get_event_bus().unsubscribe(PROCESS_STATUS_CHANGED, on_process_status)
            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=2)
            self.config.sync_all_account_paths()
            # 广播会话生命周期结束事件
            get_event_bus().publish(Event(
                APP_COMPLETION,
                AppCompletionEvent(success=True, message="会话已正常结束"),
            ))
