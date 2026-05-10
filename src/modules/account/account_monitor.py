# -*- coding: utf-8 -*-
import time
from datetime import datetime
from pathlib import Path

from src.modules.account.account_operations import restore_default
from src.modules.logger import Logger


class AccountMonitor:
    """账户监控：观察登录成功并触发密钥同步"""

    def __init__(self, tag: str, check_tag: str | None, config_manage, logger: Logger, spawn_time: datetime | None = None):
        self.tag = tag
        self.check_tag = check_tag
        self.config = config_manage
        self.logger = logger
        self.spawn_time = spawn_time or datetime.now()
        self.configs_file = Path(config_manage.path) / "tdata" / "D877F783D5D3EF8C" / "configs"

    def run(self):
        """监控循环"""
        # self.logger.info("状态监控运行中")
        is_logged_in = False
        monitor_started = False

        try:
            while True:
                if self.config.process_status:
                    if not is_logged_in:
                        if self.configs_file.exists() and self.configs_file.stat().st_mtime >= self.spawn_time.timestamp():
                            self.logger.info(f"账户登录成功")
                            is_logged_in = True
                            self.config.start_time = datetime.now()
                            monitor_started = True
                else:
                    # 进程关闭
                    if self.tag and self.tag != self.config.default:
                        self.logger.info("正在恢复默认账户")

                        if monitor_started:
                            running_time = datetime.now() - self.config.start_time
                            if not is_logged_in:
                                is_logged_in = (self.configs_file.exists() and
                                                self.configs_file.stat().st_mtime >= self.spawn_time.timestamp())

                            if running_time.total_seconds() >= 60 and is_logged_in:
                                self.logger.info(f"符合同步条件，更新密钥 -> '{self.tag}'")
                                self.config.backup_account_keys(self.tag, Path(self.config.path) / "tdata")

                        restore_default()
                    break
                time.sleep(1)
        except Exception as e:
            self.logger.exception("状态监控线程异常", e)
        finally:
            self.config.sync_all_account_paths()
            self.config.complete = True
