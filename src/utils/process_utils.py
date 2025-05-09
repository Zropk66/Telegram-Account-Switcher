# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import asyncio
import atexit
import os

import psutil

from src.utils.logger import logger


def check_process_is_run(client: str):
    if not isinstance(client, str):
        raise TypeError("'client' must be 'str'")
    for process in psutil.process_iter(attrs=['name']):
        try:
            if client == process.name():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(e)
    return False


async def async_check_process_is_run(
        client: str,
        max_retries: int = 5,
        base_delay: float = 0.5,
        timeout: float = 30.0
) -> bool:
    """
    异步进程检测

    :param client: 进程名称
    :param max_retries: 最大重试次数
    :param base_delay: 基础等待间隔
    :param timeout: 总超时时间
    :return: 进程是否存活
    """
    start_time = asyncio.get_event_loop().time()

    async def _check_once() -> bool:
        """单次检测封装"""
        try:
            return check_process_is_run(client)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug(f"进程检测异常: {str(e)}")
            return False

    for attempt in range(max_retries):
        delay = base_delay * (2 ** attempt)
        deadline = start_time + timeout

        try:
            return await asyncio.wait_for(
                _check_once(),
                timeout=min(delay, deadline - asyncio.get_event_loop().time())
            )
        except asyncio.TimeoutError:
            if asyncio.get_event_loop().time() > deadline:
                logger.warning(f"进程检测超时: {client}")
                return False
            continue

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


def safe_exit(message=None, restore=False):
    """退出程序"""
    from src.utils.files_utils import config_helper
    client = config_helper(field='client', mode='r')
    try_kill_process(client)
    if restore:
        from src.utils.files_utils import modify_file
        modify_file('restore')
    logger.info('程序结束.')
    from src.utils.files_utils import restore_file
    atexit.unregister(restore_file)
    from src.main import WORK_PATH
    open(os.path.join(WORK_PATH, "TAS_log.txt"), 'a', encoding='utf-8').write(
        '----------------------------------------\n')
    from src.main import lock
    lock.close()
    raise SystemExit(message)
