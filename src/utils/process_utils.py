# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import atexit
import os

import psutil

from src.utils.config_manage import ConfigManage
from src.utils.logger import Logger


def check_process_alive(client: str):
    if not isinstance(client, str):
        raise TypeError("'client' must be 'str'")
    for process in psutil.process_iter(attrs=['name']):
        try:
            if client == process.name(): return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            Logger().error(e)
    return False


def try_kill_process(client: str):
    if not isinstance(client, str):
        raise TypeError("'client' must be 'str'")
    for process in psutil.process_iter(['name']):
        process_name = process.info['name']
        if client == process_name:
            try:
                process.terminate()
                return True
            except psutil.NoSuchProcess:
                return True
            except (PermissionError, psutil.AccessDenied) as e:
                Logger().error(e, exc_info=True)
    return False


def try_find_client(clients: list):
    if not isinstance(clients, list):
        raise TypeError("'clients' must be 'list'")
    black_list = ['sogouimebroker', 'runtimebroker', 'ChsIME', 'DynamicDependencyLifetimeManagerShadow']
    for process in psutil.process_iter(['name']):
        try:
            process_name = process.info['name']
            if any(keyword.lower() in process_name.lower() for keyword in black_list):
                continue
            if any(keyword.lower() in process_name.lower() for keyword in clients):
                return process_name
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            Logger().error(e)
    return None


def get_process_path(client: str):
    if not isinstance(client, str):
        raise TypeError("'client' must be 'str'")
    for process in psutil.process_iter(['name', 'exe']):
        try:
            process_name = process.info['name']
            if client == process_name:
                return os.path.dirname(process.info['exe'])
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            Logger().error(e)
    return None


def safe_exit(message=None, restore=False, kill_process=False):
    """退出程序"""
    config = ConfigManage()
    if kill_process:
        try_kill_process(config.client)
    if restore:
        from src.utils.files_utils import account_switch
        account_switch('restore')
    Logger().info('任务完成!')
    from src.utils.files_utils import recovery
    atexit.unregister(recovery)
    if config.log_output:
        with open(os.path.join(os.getcwd(), "TAS.log"), 'a', encoding='utf-8') as f:
            f.write('----------------------------------------\n')
    # from src.main import lock
    # lock.close()
    raise SystemExit(message)
