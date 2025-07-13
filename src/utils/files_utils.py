# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import asyncio
import atexit
import os
import random
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional

from src.utils.config_manage import ConfigManage
from src.utils.logger import Logger
from src.utils.system_utils import format_timedelta
from src.utils.exceptions import TASException


class AccountSwitcher:
    """账户切换器"""

    def __init__(self):
        self.logger = Logger()
        self._config = ConfigManage()

    def process(self):
        """账户切换器启动函数"""
        tag = self._config.tag
        try:
            if not asyncio.run(self.__process(tag)):
                self.logger.error('客户端启动超时.')
                return False
            if is_exists(os.path.join(self._config.path, 'tdata'), 'main'):
                self.logger.info('客户端启动成功.')
                return True
        except Exception as e:
            self.logger.error(e)
            return True
        self.logger.info('客户端启动成功, 运行状况持续受到监控.')
        start_time = datetime.now()
        while True:
            if not self._config.process_status:
                end_time = datetime.now()
                self.logger.info(f"监控时长：{format_timedelta(end_time - start_time)}.")
                account_switch('restore')
                break
            time.sleep(0.1)
        return True

    async def __process(self, tag) -> Optional[bool]:
        """账户切换器工作函数"""
        for i in range(30):
            tags = self._config.tags
            if tag not in tags:
                if is_exists(os.path.join(self._config.path, 'tdata'), self._config.default):
                    self.run_command()
                    return True
                else:
                    if account_switch('restore'):
                        self.logger.info('账户已切换为默认账户.')
                        self.run_command()
                    else:
                        self.logger.error('切换默认账户失败.')
                self.logger.info('客户端已启动.')
                return True
            atexit.register(recovery)
            if is_exists(os.path.join(self._config.path, 'tdata'), tag):
                startup_successful = self.run_command()
            else:
                if account_switch('target'):
                    self.logger.info(f"已切换为目标账户 -> '{tag}'.")
                    startup_successful = self.run_command()
                else:
                    return False
            return startup_successful
        return False

    def run_command(self):
        """客户端启动函数"""
        client_path = os.path.join(self._config.path, self._config.client)
        try:
            subprocess.Popen(
                [str(client_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                shell=True,
                start_new_session=True
            )
            while True:
                if self._config.process_status:
                    break
                time.sleep(0.1)
            return True
        except FileNotFoundError:
            self.logger.error(f"客户端路径不存在: {client_path}")
        except Exception as e:
            self.logger.error(f"启动异常: {str(e)}")
        return False


def account_switch(mode: str, retries=0, max_retries=5):
    """控制账户的切换与还原"""
    config = ConfigManage()
    tag = sys.argv[-1]
    if retries >= max_retries:
        raise TASException('权限不足，账户切换失败')
    random_str = ''.join(random.sample('ABCDEFGH', 5))
    temp = f'tdata-{random_str}'
    try:
        if mode == 'restore':
            result = switch_to_default(config.path, config.default, temp)
        elif mode == 'target':
            result = switch_to_target(config.path, tag, temp)
        else:
            raise TASException(f"模式 ‘{mode}’ 未定义")
        return result
    except PermissionError:
        time.sleep(1)
        return account_switch(mode, retries + 1, max_retries)


def switch_to_default(path, default, temp):
    """切换回默认账户"""
    try:
        try:
            os.rename(os.path.join(path, 'tdata'), os.path.join(path, temp))
        except FileNotFoundError:
            pass
        os.rename(
            os.path.join(path, search_file_in_dirs(path, default)),
            os.path.join(path, 'tdata'))
        return True
    except PermissionError:
        return False


def switch_to_target(path, arg, temp):
    """切换为目标账户"""
    try:
        try:
            target_dir = os.path.join(path, search_file_in_dirs(path, arg))
        except TypeError:
            return False
        os.rename(os.path.join(path, 'tdata'), os.path.join(path, temp))
        os.rename(target_dir, os.path.join(path, 'tdata'))
        return True
    except PermissionError:
        return False


def recovery():
    """强制恢复为默认账户"""
    try:
        from src.utils.process_utils import try_kill_process
        try_kill_process(ConfigManage().client)
        time.sleep(1)
        account_switch('restore')
    except (FileNotFoundError, PermissionError):
        pass


def search_file_in_dirs(base_path: str, target_file: str):
    """在文件夹中查找目标文件并返回具体路径"""
    if not os.path.isdir(base_path):
        return ''

    for entry in os.scandir(base_path):
        if entry.is_dir():
            file_path = os.path.join(entry.path, target_file)
            if os.path.isfile(file_path):
                return entry.name
    return ''


def is_exists(base_path: str, target_file: str):
    """判断文件夹中是否存在目标文件"""
    try:
        if os.path.exists(os.path.join(base_path, target_file)):
            return True
        else:
            return False
    except (FileNotFoundError, PermissionError, TypeError):
        return False


def validate_path(path: str) -> bool:
    """路径有效性验证"""
    return os.path.exists(path) and os.path.isfile(path)
