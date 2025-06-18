# -*- coding: utf-8 -*-
# @Time : 2025/1/2 13:12
# @Author : Zropk
import argparse
import atexit
import os
import os.path
import sys
from typing import Optional

from PySide6.QtWidgets import QApplication

from src.ui import SettingsWindow
from src.utils import Logger, search_file_in_dirs, recovery, ConfigManage, try_kill_process, handle_global_exception, \
    TdataProcess

logger = Logger()
TITLE = 'TAS'
VERSION = '1.1.3'

CONFIG_FILE = 'configs.json'
CONFIG = ConfigManage()

def open_setting_window():
    """打开设置窗口"""
    app = QApplication.instance() or QApplication(sys.argv)
    widget = SettingsWindow()
    widget.show()
    sys.exit(app.exec())


def check_client(client):
    """检查客户端"""
    path = CONFIG.path
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
    if not search_file_in_dirs(CONFIG.path, default_tdata):
        logger.tips(f"默认帐户配置无效, 未找到标签为 '{default_tdata}' 的帐户文件夹")
        return False
    return True


def parse_arguments() -> argparse.Namespace:
    """参数解析"""
    parser = argparse.ArgumentParser(
        description='参数解析器',
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
        return CONFIG.default

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
    tags = CONFIG.tags
    if tag == CONFIG.default:
        return tag

    if tag not in tags:
        logger.warning(f"未注册的标签: {tag}")
        return CONFIG.default

    if not search_file_in_dirs(CONFIG.path, tag):
        logger.error(f"标签文件缺失 {tag}")
        return CONFIG.default
    return tag


def check_configs():
    CONFIG.tag = str(check_argument())
    if check_client(CONFIG.client) is False:
        logger.tips('客户端检查失败.')
        return False
    if check_path(CONFIG.path) is False:
        logger.tips('路径检查失败.')
        return False
    if check_default_tdata(CONFIG.default) is False:
        logger.tips('默认标签检查失败.')
        return False
    return True


def initialize():
    """初始化函数"""
    sys.excepthook = handle_global_exception
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
    # try:
    #     if isinstance(args, tuple):
    #         sys.argv = ['program.py'] + ''.join(args).split(' ')
    # except IndexError:
    #     pass
    initialize()
    try_kill_process(CONFIG.client)
    atexit.register(recovery)
    TdataProcess().process()
    atexit.unregister(recovery)
    logger.info('任务完成!')
