# -*- coding: utf-8 -*-
# @Time : 2025/1/2 13:12
# @Author : Zropk
import argparse
import asyncio
import atexit
import os
import os.path
import subprocess
import sys
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import QApplication

from src.ui.settings import MainWindow
from src.utils.files_utils import search_target_file_in_directories, is_exists, restore_file, modify_file, \
    config_manager
from src.utils.logger import logger
from src.utils.process_utils import safe_exit, try_kill_process, check_process_alive
from src.utils.system_utils import handle_global_exception, bind_singleton, format_timedelta

logger = logger
TITLE = 'TAS'
VERSION = '1.1.2'

CONFIG_FILE = 'configs.json'
CONFIG = config_manager()

lock = bind_singleton(9564)


def open_setting_window():
    """打开设置窗口"""
    app = QApplication.instance() or QApplication(sys.argv)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())


def tdata_process():
    """判断 tdata 状态并执行相关操作"""
    try:
        tag = CONFIG.get('tag')
        if asyncio.run(__tdata_process(tag)) is False:
            logger.error('客户端启动超时.')
            safe_exit()
        logger.info('客户端启动成功, 运行状况持续受到监控.')
        start_time = datetime.now()

        while True:
            alive = check_process_alive(CONFIG.get('client'))
            if alive is False:
                end_time = datetime.now()
                logger.info(f"监控时长：{format_timedelta(end_time - start_time)}")
                break

        safe_exit(restore=True)
    except Exception:
        logger.error('参数解析失败.', exc_info=True)
        safe_exit(restore=True)


async def __tdata_process(tag):
    """异步检查客户端是否启动"""
    for i in range(30):
        tags = CONFIG.get('tags')
        if tag not in tags:
            if is_exists(os.path.join(CONFIG.get('path'), 'tdata'), CONFIG.get('default')):
                run_command()
            else:
                if modify_file('restore'):
                    run_command()
            logger.info('客户端启动.')
            safe_exit()
        atexit.register(restore_file)
        startup_successful = False
        if is_exists(os.path.join(CONFIG.get('path'), 'tdata'), tag):
            run_command()
            startup_successful = True
        else:
            if modify_file('modify'):
                run_command()
                startup_successful = True
            else:
                safe_exit(restore=True)
        return startup_successful
    return False


def run_command():
    """启动目标程序"""
    client_path = os.path.join(CONFIG.get('path'), CONFIG.get('client'))
    try:
        proc = subprocess.Popen(
            [str(client_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            shell=True,
            start_new_session=True
        )
        while True:
            alive = check_process_alive(CONFIG.get('client'))
            if alive:
                break
        return proc
    except FileNotFoundError:
        logger.error(f"客户端路径不存在: {client_path}")
    except Exception as e:
        logger.error(f"启动异常: {str(e)}")
    return None

def check_client(client):
    """检查客户端"""
    path = CONFIG.get('path')
    if os.path.isfile(os.path.join(path, client)):
        return True
    logger.warning('无法找到客户端.')
    return False


def check_path(path):
    """检查路径"""
    if os.path.isdir(path):
        return True
    logger.warning('路径格式不正确.')
    return False


def check_default_tdata(default_tdata):
    """检查默认标签"""
    if default_tdata == '':
        logger.warning('未设置默认 Tdata.')
        return False
    if not search_target_file_in_directories(CONFIG.get('path'), default_tdata):
        logger.tips(f"默认帐户配置无效, 未找到标签为 '{default_tdata}' 的帐户文件夹")
        return False
    return True


def parse_arguments() -> argparse.Namespace:
    """参数解析"""
    parser = argparse.ArgumentParser(
        description='应用参数解析器',
        add_help=False,
        exit_on_error=False
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--version',
                       action='store_true',
                       help='显示当前版本')
    group.add_argument('--settings',
                       action='store_true',
                       help='打开设置窗口')
    group.add_argument('--login',
                       type=str,
                       metavar='tag',
                       help='登录指定标签的账号')

    parser.add_argument('--help',
                        action='store_true',
                        help='显示帮助文档')
    return parser.parse_args()


def check_argument() -> Optional[str]:
    """参数处理方法"""
    try:
        args = parse_arguments()
    except argparse.ArgumentError:
        return CONFIG.get('default')

    if args.help:
        logger.tips("--version -> 获取版本\n"
                    "--help -> 帮助文档\n"
                    "--setting -> 打开设置\n"
                    "--login -> 登录指定标签的账号\n")
        sys.exit()

    if args.version:
        logger.tips(f'{TITLE} v{VERSION}')
        sys.exit()

    if args.settings:
        open_setting_window()
        sys.exit()

    if args.login:
        return validate_login_tag(args.login)
    return None


def validate_login_tag(tag: str) -> str:
    """验证登录标签"""
    tags = CONFIG.get('tags')
    if tag == CONFIG.get('default'):
        return tag

    if tag not in tags:
        logger.warning(f"未注册的标签: {tag}")
        return CONFIG.get('default')

    if not search_target_file_in_directories(CONFIG.get('path'), tag):
        logger.error(f"标签文件缺失 {tag}")
        return CONFIG.get('default')
    return tag

def check_configs():
    if check_client(CONFIG.get('client')) is False:
        logger.tips('客户端检查失败.')
        return False
    if check_path(CONFIG.get('path')) is False:
        logger.tips('路径检查失败.')
        return False
    if check_default_tdata(CONFIG.get('default')) is False:
        logger.tips('默认标签检查失败.')
        return False
    CONFIG.set('tag', check_argument())
    return True


def initialize():
    """初始化函数"""
    sys.excepthook = handle_global_exception

    if lock is False:
        logger.tips('当前已有实例正在运行.')
        sys.exit()
    if not os.path.exists(os.path.join(os.getcwd(), CONFIG_FILE)):
        logger.warning(f'配置文件 {os.path.join(os.getcwd(), CONFIG_FILE)} 不存在')
        open_setting_window()
    else:
        try:
            if check_configs() is False:
                open_setting_window()
                sys.exit()
        except Exception as e:
            logger.error('客户端初始化失败, 请检查设置是否正确.')
            logger.critical(e, exc_info=True)
            open_setting_window()
    logger.info('初始化成功.')


def main():
    """主函数"""
    initialize()
    try_kill_process(CONFIG.get('client'))
    atexit.register(restore_file)
    tdata_process()
    atexit.unregister(restore_file)
    logger.info('程序运行结束.')
