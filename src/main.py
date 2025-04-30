# -*- coding: utf-8 -*-
# @Time : 2025/1/2 13:12
# @Author : DecadeX
import atexit
import ctypes
import os
import os.path
import socket
import subprocess
import sys
import time
import traceback

from PySide6.QtWidgets import QApplication

from src.ui.settings import MainWindow
from src.utils.files_utils import search_target_file_in_directories, is_exists, restore_file, modify_file, config_helper
from src.utils.logger import logger
from src.utils.process_utils import handle_process, system_exit
from src.utils.system import ctrl_handler, handle_global_exception

__version__ = 1.0
TITLE = 'TAS'
VERSION = '1.0'
WORK_PATH = os.getcwd()
logger = logger
CLIENT = 'Telegram.exe'
PATH = ''
DEFAULT = ''
ARGS = []
ARG = ''


def check_singleton(port):
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        lock_socket.bind(('0.0.0.0', port))
        lock_socket.listen()
        return lock_socket
    except socket.error:
        return False


lock = check_singleton(9564)


def start_setting_window():
    """打开设置窗口"""
    app = QApplication.instance() or QApplication(sys.argv)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())


def set_value(name: str, value):
    """设置全局变量"""
    global CLIENT, PATH, DEFAULT, ARGS, ARG
    try:
        if name == 'client':
            CLIENT = value
        if name == 'path':
            PATH = value
        if name == 'default':
            DEFAULT = value
        if name == 'args':
            ARGS = list(value)
        if name == 'arg':
            ARG = value
            return
        config_helper(field=name, mode='w', value=value)
    except Exception as e:
        logger.error(f'{name} 设置失败.')
        logger.critical(e)


def tdata_process():
    """判断 tdata 状态并执行相关操作"""
    try:
        if not ARG:
            not_arg()
            return

        while True:
            if has_arg():
                logger.info('客户运行状况持续受到监控.')
                break
        isRunning = True
        while isRunning:
            time.sleep(1)
            isRunning = handle_process(client=CLIENT, mode='isRun')
        logger.info('客户端已关闭.')
        system_exit(restore=True)
    except Exception:
        logger.error('参数解析失败.')
        system_exit(restore=True)

def run_command():
    command = f'start "" "{os.path.join(PATH, CLIENT)}"'
    return subprocess.Popen(command, shell=True, cwd=PATH)

def not_arg():
    if is_exists(os.path.join(PATH, 'tdata'), DEFAULT):
        run_command()
        logger.info('客户端启动.')
    else:
        if modify_file('restore'):
            run_command()
            logger.info('客户端启动.')
    system_exit()

def has_arg() -> bool:
    atexit.register(restore_file)
    startupSuccessful = False
    if is_exists(os.path.join(PATH, 'tdata'), ARG):
        run_command()
        startupSuccessful = True
        logger.info('无需切换账户.')
    else:
        if modify_file('modify'):
            run_command()
            startupSuccessful = True
        else:
            system_exit(restore=True)
    return startupSuccessful


def check_client():
    """检查客户端是否正确"""
    client = config_helper(field='client', mode='r')
    path = config_helper(field='path', mode='r')
    if os.path.isfile(os.path.join(path, client)):
        global CLIENT
        CLIENT = client
        return client
    logger.tips('无法找到客户端.')
    start_setting_window()
    sys.exit()


def check_path():
    """检查路径是否正确"""
    path = config_helper(field='path', mode='r')
    if os.path.isdir(path):
        return path
    logger.tips('路径格式不正确.')
    start_setting_window()
    sys.exit()


def check_default_tdata():
    """获取默认登录账户"""
    default_tdata = str(config_helper(field='default', mode='r'))
    if default_tdata is None or default_tdata == '':
        config_helper(field='default', mode='w', value='')
        logger.tips('未设置默认 Tdata.')
        start_setting_window()
        sys.exit()
    if not search_target_file_in_directories(PATH, default_tdata):
        logger.tips(f"默认帐户配置无效, 未找到标签为 '{default_tdata}' 的帐户文件夹")
        start_setting_window()
        sys.exit()

    return default_tdata


def check_arg():
    """处理参数"""
    tdatas = config_helper(field='args', mode='r')
    try:
        argument = ''
        if len(sys.argv) == 1:
            return ''
        if len(sys.argv) <= 3:
            try:
                argument = sys.argv[1].split('--')[1]
            except IndexError:
                logger.error('参数解析错误.')
                return ''

            if argument.lower() == 'help':
                logger.tips("--help -> 帮助文档\n--setting -> 打开设置\n--login -> 登录指定标签的账号")
                sys.exit()
            elif argument.lower() == 'settings':
                logger.info('打开设置.')
                start_setting_window()
                sys.exit()
            elif argument.lower() == 'login':
                argument = sys.argv[-1]
                if argument is None or argument == '' or argument == '--login':
                    return ''
                if argument not in tdatas:
                    if argument == config_helper(field='default', mode='r'):
                        return ''
                    logger.tips(
                        f"参数 '{argument}' 尚未注册.\n"
                        f"您可以使用 '-setting' 参数打开设置来添加它.")
                    system_exit()
                if not search_target_file_in_directories(PATH, argument):
                    logger.tips(f"无法找到标签为 '{argument}'")
                    return ''
                return argument
        else:
            logger.tips(f"参数过多.")
        logger.info(f"未知参数 '{argument}'.")
        return ''
    except ValueError as e:
        logger.critical("".join(traceback.format_exception(type(e), e, e.__traceback__)))
        system_exit()
        return None


def initialize():
    """初始化函数"""
    sys.excepthook = handle_global_exception
    kernel32 = ctypes.WinDLL("kernel32")
    HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
    handleCtrl = HandlerRoutine(ctrl_handler)
    kernel32.SetConsoleCtrlHandler(handleCtrl, True)
    if lock is False:
        logger.tips('当前已有实例正在运行.')
        sys.exit()
    if not os.path.exists('configs.json'):
        start_setting_window()
    else:
        try:
            set_value('client', check_client())
            set_value('path', check_path())
            set_value('default', check_default_tdata())
            set_value('args', config_helper(field='args', mode='r'))
            set_value('arg', check_arg())
        except Exception as e:
            logger.error('客户端初始化失败, 请检查设置是否正确.')
            logger.critical(e)
            start_setting_window()
    logger.info('初始化成功.')


def main():
    """主函数"""
    initialize()
    handle_process(client=CLIENT, mode='kill')
    atexit.register(restore_file)
    tdata_process()
    atexit.unregister(restore_file)
    logger.info('程序运行结束.')
