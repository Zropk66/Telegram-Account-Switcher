# -*- coding: utf-8 -*-
# @File ： AccountSwitcher.py
# @Time : 2025/8/5 23:45
# @Author : Zropk

import asyncio
import atexit
import os
import time
from datetime import datetime

from src.modules.account.account_operations import account_switch, recovery
from src.modules.utils import search_file_in_dirs, is_exists, format_timedelta
from src.modules.process_manager import ProcessManager
from src.modules.config_manager import ConfigManage
from src.modules.logger import Logger


class AccountSwitcher:
    """账户切换器"""

    def __init__(self):
        self.logger = Logger()
        self._config = ConfigManage()

    def _cleanup_orphan_folders(self):
        """清理并恢复孤儿 tdata 文件夹"""
        path = self._config.path
        if not path or not os.path.isdir(path):
            return

        tdata_path = os.path.join(path, "tdata")
        # 如果 tdata 不存在，尝试找备份恢复
        if not os.path.exists(tdata_path):
            for entry in os.scandir(path):
                if entry.is_dir() and entry.name.startswith("tdata-"):
                    try:
                        self.logger.warning(
                            f"检测到异常中断，正在从 {entry.name} 恢复..."
                        )
                        os.rename(entry.path, tdata_path)
                        return  # 恢复一个即可
                    except OSError:
                        continue

    def process(self):
        """账户切换器启动函数"""
        self._cleanup_orphan_folders()  # 启动时先自愈
        tag = self._config.tag
        self._config.has_backup = os.path.isfile(
            os.path.join(
                self._config.path,
                search_file_in_dirs(self._config.path, self._config.tag),
                "key_datas.bak",
            )
        )
        try:
            if not asyncio.run(self.__process(tag)):
                self.logger.error("客户端启动超时.")
                return False
            if is_exists(os.path.join(self._config.path, "tdata"), "main"):
                self.logger.info("客户端启动成功.")
                return True
        except Exception as e:
            self.logger.exception("", e)
            return True
        self.logger.info("客户端启动成功, 状态监控器运行中...")
        self._config.start_time = datetime.now()
        while True:
            if not self._config.process_status:
                account_switch("restore")
                break
            time.sleep(0.1)
        return True

    async def __process(self, tag: str) -> bool:
        """账户切换器工作函数"""
        process_manager = ProcessManager()
        tags = self._config.tags

        # 处理默认账户或未定义标签
        if tag not in tags:
            tag_exists = is_exists(
                os.path.join(self._config.path, "tdata"), self._config.default
            )
            if account_switch(method="restore", tag_in_folder=tag_exists):
                return process_manager.start_process(self._config)
            else:
                self.logger.error("切换默认账户失败.")
                return False

        # 尝试切换到目标账户并启动
        if account_switch(
            method="target",
            tag_in_folder=is_exists(os.path.join(self._config.path, "tdata"), tag),
        ):
            self.logger.info(f"已切换为目标账户 -> '{tag}'.")
            return process_manager.start_process(self._config)
        else:
            self.logger.error(f"切换到目标账户 '{tag}' 失败.")
            return False
