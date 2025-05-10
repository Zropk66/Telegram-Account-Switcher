# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import atexit
import os

import psutil

from src.utils.files_utils import config_manager
from src.utils.logger import logger


def check_process_alive(client: str):
    if not isinstance(client, str):
        raise TypeError("'client' must be 'str'")
    for process in psutil.process_iter(attrs=['name']):
        try:
            if client == process.name():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(e)
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
                logger.error(e, exc_info=True)
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
            logger.error(e)
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
            logger.error(e)
    return None


def safe_exit(message=None, restore=False, kill_process=False):
    """退出程序"""
    config = config_manager()
    client = config.get('client')
    if kill_process:
        try_kill_process(client)
    if restore:
        from src.utils.files_utils import modify_file
        modify_file('restore')
    logger.info('程序结束.')
    from src.utils.files_utils import restore_file
    atexit.unregister(restore_file)
    if config.get('log_output'):
        open(os.path.join(os.getcwd(), "TAS_log.txt"), 'a', encoding='utf-8').write(
            '----------------------------------------\n')
    from src.main import lock
    lock.close()
    raise SystemExit(message)
