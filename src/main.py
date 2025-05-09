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
import time
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication

from src.ui.settings import MainWindow
from src.utils.files_utils import search_target_file_in_directories, is_exists, restore_file, modify_file, \
    config_manager
from src.utils.logger import logger
from src.utils.process_utils import safe_exit, async_check_process_is_run, try_kill_process
from src.utils.system_utils import handle_global_exception, bind_singleton

logger = logger
TITLE = 'TAS'
VERSION = '1.1.0'
WORK_PATH = os.getcwd()

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
        if not tag:
            not_tag()
            logger.info('客户端启动.')
            safe_exit()

        if asyncio.run(async_wait_process_is_run(tag)) is False:
            logger.error('客户端启动超时.')
            safe_exit()
        logger.info('客户端启动成功, 运行状况持续受到监控.')
        time.sleep(1)

        asyncio.run(async_check_process_is_run(CONFIG.get('client'), 114514000, 1))
        safe_exit(restore=True)
    except Exception:
        logger.error('参数解析失败.', exc_info=True)
        safe_exit(restore=True)


async def async_wait_process_is_run(tag):
    for i in range(30):
        if has_tag(tag):
            return True
    return False


def run_command():
    client_path = Path(CONFIG.get('path')) / CONFIG.get('client')
    try:
        client_path = client_path.resolve(strict=True)

        proc = subprocess.Popen(
            [str(client_path)],
            cwd=str(client_path.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            shell=True,
            start_new_session=True
        )
        return proc
    except FileNotFoundError:
        logger.error(f"客户端路径不存在: {client_path}")
    except Exception as e:
        logger.error(f"启动异常: {str(e)}")
    return None


def not_tag():
    if is_exists(os.path.join(CONFIG.get('path'), 'tdata'), CONFIG.get('default')):
        run_command()
    else:
        if modify_file('restore'):
            run_command()


def has_tag(tag) -> bool:
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


def check_client(client):
    """检查客户端是否正确"""
    path = CONFIG.get('path')
    if os.path.isfile(os.path.join(path, client)):
        return True
    logger.warning('无法找到客户端.')
    return False


def check_path(path):
    """检查路径是否正确"""
    if os.path.isdir(path):
        return True
    logger.warning('路径格式不正确.')
    return False


def check_default_tdata(default_tdata):
    """检查默认登录账户"""
    if default_tdata == '':
        logger.warning('未设置默认 Tdata.')
        return False
    if not search_target_file_in_directories(CONFIG.get('path'), default_tdata):
        logger.tips(f"默认帐户配置无效, 未找到标签为 '{default_tdata}' 的帐户文件夹")
        return False
    return True


def parse_arguments() -> argparse.Namespace:
    """使用标准库实现参数解析"""
    parser = argparse.ArgumentParser(
        description='应用参数解析器',
        add_help=False
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
    """重构后的参数处理方法"""
    try:
        args = parse_arguments()

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

    except argparse.ArgumentError as e:
        logger.error(f"参数解析错误: {str(e)}")
        sys.exit(1)


def validate_login_tag(tag: str) -> str:
    """验证登录标签"""
    tags = CONFIG.get('tags')

    if tag not in tags:
        logger.warning(f"未注册的标签: {tag}")
        return CONFIG.get('default')

    if not search_target_file_in_directories(CONFIG.get('path'), tag):
        logger.error(f"标签文件缺失 {tag}")
        return CONFIG.get('default')
    return tag


def initialize():
    """初始化函数"""
    sys.excepthook = handle_global_exception

    if lock is False:
        logger.tips('当前已有实例正在运行.')
        sys.exit()
    if not os.path.exists(os.path.join(WORK_PATH, CONFIG_FILE)):
        logger.warning(f'配置文件 {os.path.join(WORK_PATH, CONFIG_FILE)} 不存在')
        open_setting_window()
    else:
        try:
            if check_client(CONFIG.get('client')) is False:
                logger.tips('客户端检查失败.')
            if check_path(CONFIG.get('path')) is False:
                logger.tips('路径检查失败.')
            if check_default_tdata(CONFIG.get('default')) is False:
                logger.tips('默认标签检查失败.')
            CONFIG.set('tag', check_argument())
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
