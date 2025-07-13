# -*- coding: utf-8 -*-
# @Time : 2025/1/2 13:12
# @Author : Zropk
import argparse
import asyncio
import atexit
import datetime
import os
import os.path
import sys
import threading
import time
from typing import Optional

from src.ui import open_settings_window
from src.utils import Logger, search_file_in_dirs, recovery, ConfigManage, try_kill_process, handle_global_exception, \
    AccountSwitcher, TASConfigException, ProcessWatcher

logger = Logger()
TITLE = 'TAS'
VERSION = '1.1.4'

CONFIG = ConfigManage()


def check_client(client) -> Optional[bool]:
    """客户端检查"""
    path = CONFIG.path
    if not os.path.isfile(os.path.join(path, client)):
        raise TASConfigException('无法找到客户端')
    return True


def check_path(path) -> Optional[bool]:
    """路径检查"""
    if not os.path.isdir(path):
        raise TASConfigException('路径格式不正确')
    return True


def check_default(default_tdata) -> Optional[bool]:
    """默认账户检查"""
    if default_tdata == '':
        raise TASConfigException('默认的账户未设置')
    if not search_file_in_dirs(CONFIG.path, default_tdata):
        raise TASConfigException(
            f"默认账户配置无效, 标记为'{default_tdata}'的账户文件夹未找到"
        )
    return True


def parse_arguments() -> argparse.Namespace:
    """参数解析"""
    parser = argparse.ArgumentParser(
        description='参数解析器',
        add_help=False,
        exit_on_error=False
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-v', '--version',
                       action='store_true',
                       help='获取当前版本')
    group.add_argument('--settings',
                       action='store_true',
                       help='打开设置窗口')
    group.add_argument('-s', '--switch',
                       type=str,
                       metavar='tag',
                       help='切换指定标签的账号')
    parser.add_argument('-h', '--help',
                        action='store_true',
                        help='获取帮助文档')
    return parser.parse_args()


def check_argument() -> Optional[str]:
    """参数处理"""
    try:
        args = parse_arguments()
    except argparse.ArgumentError:
        return CONFIG.default
    if args.help:
        logger.info(
            "\n--version | -v -> 获取版本\n"
            "--help | -h -> 帮助文档\n"
            "--setting -> 打开设置\n"
            "--switch | -s -> 切换指定标签的账号",
            popup=True
        )
    elif args.version:
        logger.info(f'{TITLE} v{VERSION}', popup=True)
    elif args.settings:
        open_settings_window()
        logger.info('打开设置窗口.')
    elif args.switch:
        return validate_tag(args.switch)
    else:
        return CONFIG.default
    sys.exit()


def validate_tag(tag: str) -> Optional[str]:
    """标签检查"""
    tags = CONFIG.tags
    if tag == CONFIG.default:
        return tag

    if tag not in tags:
        logger.warning(f"未注册的标签: {tag}")
        return CONFIG.default

    if not search_file_in_dirs(CONFIG.path, tag):
        logger.warning(f"标签文件缺失 {tag}")
        return CONFIG.default
    return tag


def check_configs() -> Optional[bool]:
    """配置文件初始化检查"""
    try:
        CONFIG.tag = str(check_argument())
        check_client(CONFIG.client)
        check_path(CONFIG.path)
        check_default(CONFIG.default)
        return True
    except TASConfigException as e:
        logger.error(f'配置验证失败, {e.message}.', popup=True)
        return False
    except Exception as e:
        raise e


async def status_handler(is_alive: bool):
    """监控回调"""
    CONFIG.process_status = is_alive


def run_async_in_thread(loop, coro):
    """启动后台监视器线程"""
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


async def watcher():
    """后台进程监控器"""
    process_watcher = ProcessWatcher(CONFIG.client)
    process_watcher.add_callback(status_handler)
    await process_watcher.start_watching()
    while True:
        complete = CONFIG.complete
        if complete:
            await process_watcher.stop_watching()
            break
        await asyncio.sleep(1)


def initialize() -> Optional[bool]:
    """初始化函数"""
    sys.excepthook = handle_global_exception
    config_file = CONFIG.config_file
    if not os.path.exists(config_file):
        logger.error(f'配置文件 {config_file} 不存在.')
        open_settings_window()
    else:
        try:
            if not check_configs():
                open_settings_window()
                sys.exit()
        except Exception as e:
            logger.exception(
                '客户端初始化失败, 请重试.\n若问题依旧请联系开发者或发布Issues，开发者会尽快解决该问题.',
                e,
                popup=True
            )
            sys.exit()
    logger.info('初始化成功.')
    return True


def main(*args):
    """主函数"""
    if args:
        try:
            if isinstance(args, tuple):
                sys.argv = ['test.py'] + ''.join(args).split(' ')
        except IndexError:
            pass
    initialize()
    if try_kill_process(CONFIG.client):
        time.sleep(1.5)
    atexit.register(recovery)
    loop = asyncio.new_event_loop()
    watch_thread = threading.Thread(
        target=run_async_in_thread,
        args=(loop, watcher()),
        daemon=True
    )
    watch_thread.start()
    AccountSwitcher().process()
    atexit.unregister(recovery)
    logger.info('任务完成.')
    CONFIG.complete = True
    if CONFIG.log_output:
        with open(os.path.join(os.getcwd(), "TAS.log"), 'a', encoding='utf-8') as f:
            f.write(f'--------------------{datetime.datetime.now()}--------------------\n')
