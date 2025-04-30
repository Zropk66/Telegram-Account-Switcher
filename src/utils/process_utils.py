import atexit
import os
import traceback

import psutil

from src.utils.files_utils import config_helper
from src.utils.logger import logger


def handle_process(client, mode: str = 'isRun'):
    """程序进程相关函数，能判断程序是否运行，是否结束程序，返回程序路径"""
    client_is_list = False
    find_client = False
    if client is None or client == '':
        return False
    if isinstance(client, list):
        client_is_list = True
    elif isinstance(client, str):
        pass
    else:
        raise TypeError("'client' 只能为 'list' 或 'str' 类型")

    black_list = ['sogouimebroker', 'runtimebroker', 'ChsIME']

    for process in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            processName = process.info['name']
            if client_is_list:
                if any(keyword.lower() in processName.lower() for keyword in black_list):
                    continue
                if any(keyword.lower() in processName.lower() for keyword in client):
                    find_client = True
            else:
                if processName == client:
                    find_client = True
            if find_client:
                if mode == 'path':
                    return os.path.dirname(process.info['exe'])
                elif mode == 'kill':
                    try:
                        process.terminate()
                        return True
                    except (PermissionError, psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        traceback.print_exc(e)
                        return False
                elif mode == 'isRun':
                    return True
                elif mode == 'check':
                    return processName
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            traceback.print_exc(e)
    return False


def system_exit(message=None, restore=False):
    """退出程序"""
    client = config_helper(field='client', mode='r')
    handle_process(client=client, mode='kill')
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
