# -*- coding: utf-8 -*-
# @File ： AccountSwitcher.py
# @Time : 2025/8/5 23:45
# @Author : Zropk

import time
from datetime import datetime
from pathlib import Path

from src.modules.account.account_operations import restore_default, switch_to_tag
from src.modules.config_manager import ConfigManage
from src.modules.logger import Logger
from src.modules.process_manager import ProcessManager
from src.modules.utils import is_exists


class AccountSwitcher:
    """账户切换器"""

    def __init__(self):
        self.logger = Logger()
        self._config = ConfigManage()

    def _cleanup_orphan_folders(self):
        """异常中断恢复"""
        path_str = self._config.path
        if not path_str:
            return
        
        base_path = Path(path_str)
        if not base_path.is_dir():
            return

        tdata_path = base_path / "tdata"
        if not tdata_path.exists():
            for entry in base_path.iterdir():
                if entry.is_dir() and entry.name.startswith("tdata-"):
                    try:
                        self.logger.warning(f"检测到异常中断，正在从 {entry.name} 恢复...")
                        entry.rename(tdata_path)
                        return
                    except OSError:
                        continue

    def process(self):
        """执行切换流程"""
        self._cleanup_orphan_folders()
        tag = self._config.tag
        check_tag = None

        needs_recovery = False
        try:
            success, should_monitor = self._process()
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
            self.logger.exception("", e)
            return True
        
        if success:
            self.logger.info("状态监控运行中")
            is_logged_in = False
            configs_file = Path(self._config.path) / "tdata" / "D877F783D5D3EF8C" / "configs"
            
            monitor_started = False
            spawn_time = datetime.now()
            
            while True:
                if self._config.process_status:
                    if not is_logged_in:
                        if configs_file.exists() and configs_file.stat().st_mtime >= spawn_time.timestamp():
                            self.logger.info(f"账户登录成功 -> '{check_tag}'")
                            is_logged_in = True
                            self._config.start_time = datetime.now()
                            monitor_started = True
                else:
                    if self._config.tag and self._config.tag != self._config.default:
                        self.logger.info("正在恢复默认账户")
                        
                        if monitor_started:
                            running_time = datetime.now() - self._config.start_time
                            
                            if not is_logged_in:
                                is_logged_in = (configs_file.exists() and 
                                                configs_file.stat().st_mtime >= spawn_time.timestamp())
                            
                            # 运行超过 60s 且登录成功则同步密钥
                            if running_time.total_seconds() >= 60 and is_logged_in:
                                sync_tag = self._config.tag
                                if sync_tag:
                                    self.logger.info(f"符合同步条件，更新密钥 -> '{sync_tag}'")
                                    self._config.backup_account_keys(sync_tag, Path(self._config.path) / "tdata")
                        
                        restore_default()
                    break
                time.sleep(1)
        
        if needs_recovery:
            self.logger.warning(f"检测到账户 '{tag}' 可能损坏，执行自愈恢复...")
            target_account = self._config.get_account(tag)
            if target_account and target_account.get('folder'):
                target_path = Path(self._config.path) / target_account['folder']
                self._config.login_with_keys(tag, str(target_path))
                self.logger.info(f"账户 '{tag}' 密钥恢复完成，请重启客户端")
        
        self._config.sync_all_account_paths()
        return True

    def _process(self) -> tuple[bool, bool]:
        """切换逻辑执行"""
        tag = self._config.tag
        process_manager = ProcessManager()
        tags = self._config.tags

        if tag not in tags:
            restore_default()
            return process_manager.start_process(wait=True), True

        if switch_to_tag():
            self.logger.info(f"已切换为目标账户 -> '{tag}'.")
            return process_manager.start_process(wait=True), True
        else:
            self.logger.error(f"交换文件失败，无法切换到 '{tag}'.")
            return False, False
