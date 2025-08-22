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

    def process(self):
        """账户切换器启动函数"""
        tag = self._config.tag
        self._config.has_backup = os.path.isfile(
            os.path.join(
                self._config.path,
                search_file_in_dirs(self._config.path, self._config.tag),
                'key_datas.bak'
            )
        )
        try:
            if not asyncio.run(self.__process(tag)):
                self.logger.error('客户端启动超时.')
                return False
            if is_exists(os.path.join(self._config.path, 'tdata'), 'main'):
                self.logger.info('客户端启动成功.')
                return True
        except Exception as e:
            self.logger.exception('', e)
            return True
        self.logger.info('客户端启动成功, 运行状况持续受到监控.')
        atexit.register(recovery)
        start_time = datetime.now()
        while True:
            if not self._config.process_status:
                end_time = datetime.now()
                self.logger.info(f"监控时长：{format_timedelta(end_time - start_time)}.")
                account_switch('restore')
                break
            time.sleep(0.1)
        atexit.unregister(recovery)
        return True

    async def __process(self, tag: str) -> bool:
        """账户切换器工作函数"""
        process_manager = ProcessManager()
        for i in range(30):
            tags = self._config.tags
            if tag not in tags:
                if account_switch(
                        method='restore',
                        tag_in_folder=is_exists(
                            os.path.join(self._config.path, 'tdata'), self._config.default
                        )
                ):
                    process_manager.start_process(self._config)
                else:
                    self.logger.error('切换默认账户失败.')
                return True
            if account_switch(method='target', tag_in_folder=is_exists(os.path.join(self._config.path, 'tdata'), tag)):
                self.logger.info(f"已切换为目标账户 -> '{tag}'.")
                startup_successful = process_manager.start_process(self._config)
            else:
                return True
            return startup_successful
        return False
