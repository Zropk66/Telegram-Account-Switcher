# -*- coding: utf-8 -*-
# @Time : 2025/1/2 13:12
# @Author : Zropk
import threading
import datetime
import argparse
import asyncio
import ctypes
import sys
import os
import signal
import atexit
from contextlib import suppress

from pathlib import Path

from src.modules import (
    search_file_in_dirs,
    TASConfigException,
    AccountSwitcher,
    ProcessManager,
    ProcessMonitor,
    ConfigManage,
    AESCipher,
    recovery,
    Logger,
)
from src.ui import open_help_window, open_settings_window

logger = Logger()
TITLE = "TAS"
VERSION = "1.3.0"
CONFIG = ConfigManage()
kernel32 = ctypes.WinDLL("kernel32")


def log_and_exit(mark=False):
    with suppress(Exception):
        if mark:
            atexit.unregister(log_and_exit)
            recovery()
        if not CONFIG.log_output:
            return None
        logger.info(f"监控时长：{CONFIG.watch_time()}.")
        with open(os.path.join(os.getcwd(), "TAS.log"), "a", encoding="utf-8") as f:
            f.write(f"{'-' * 20}{datetime.datetime.now()}{'-' * 20}\n")
    return None


def register_signal_handlers():
    """注册信号处理器"""

    def handle_interrupt(signum, frame):
        log_and_exit(True)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_interrupt)


def handle_global_exception(exc_type, exc_value, exc_traceback):
    """捕获全局未处理错误"""
    if exc_type is KeyboardInterrupt or exc_type is SystemExit:
        sys.exit(0)
    logger.exception(
        f"捕获到未处理异常, 请尝试重启程序,\n若问题依旧请联系开发者或发布Issues，开发者会尽快解决该问题.",
        exc_value,
        popup=True,
    )


def parse_arguments() -> argparse.Namespace:
    """参数解析"""
    parser = argparse.ArgumentParser(
        description="参数解析器", add_help=False, exit_on_error=False
    )

    action_group = parser.add_argument_group()
    action_group.add_argument("--encrypt", "-e", action="store_true", help="立即加密")
    action_group.add_argument("--decrypt", "-d", action="store_true", help="立即解密")
    action_group.add_argument(
        "--switch", "-s", type=str, metavar="tag", help="切换指定标签的账号"
    )
    action_group.add_argument(
        "--tag", "-t", type=str, metavar="tag", help="指定要操作的标签账户"
    )

    exclusive_group = parser.add_mutually_exclusive_group()
    exclusive_group.add_argument(
        "--version", "-v", action="store_true", help="获取当前版本"
    )
    exclusive_group.add_argument(
        "--settings", "-c", action="store_true", help="打开设置窗口"
    )
    exclusive_group.add_argument(
        "--help", "-h", action="store_true", help="获取帮助文档"
    )
    parser.add_argument(
        "--password", "-p", type=str, metavar="password", help="指定解密密钥"
    )
    return parser.parse_args()


def check_argument() -> str:
    """参数处理"""
    try:
        args = parse_arguments()
    except argparse.ArgumentError:
        return CONFIG.default

    if args.password:
        CONFIG.pwd = args.password

    # 处理标签指定操作
    if args.tag:
        if not args.encrypt and not args.decrypt:
            logger.error("使用 --tag 时必须指定 --encrypt 或 --decrypt.", popup=True)
            sys.exit()
        if args.encrypt:
            process_single_tag(args.tag, "encrypt")
        else:
            process_single_tag(args.tag, "decrypt")
        sys.exit()

    if args.help:
        open_help_window(VERSION)
    elif args.version:
        logger.info(f"{TITLE} v{VERSION}", popup=True)
    elif args.settings:
        open_settings_window(VERSION)
    elif args.encrypt:
        process_tags("encrypt")
    elif args.decrypt:
        process_tags("decrypt")
    elif args.switch:
        return validate_tag(args.switch)
    else:
        return CONFIG.default
    sys.exit()


def _process_tag(tag: str, operation: str, cipher: AESCipher) -> tuple[bool, str | None]:
    """
    处理单个标签的加解密操作
    返回: (是否成功, 跳过原因/错误信息)
    """
    tag_path = search_file_in_dirs(CONFIG.path, tag)
    if not tag_path:
        return False, f"标签 '{tag}' 文件缺失"

    key_datas_path = Path(CONFIG.path) / tag_path / "key_datas"

    if not key_datas_path.exists():
        return False, f"标签 '{tag}' 的 key_datas 文件不存在"

    try:
        if operation == "encrypt":
            if AESCipher.is_encrypted(key_datas_path):
                return False, "已加密"
            cipher.encrypt(key_datas_path)
            return True, None
        else:
            cipher.decrypt(key_datas_path)
            return True, None
    except Exception as e:
        return False, str(e)


def process_tags(operation: str) -> None:
    """处理所有标签的加密/解密操作"""
    if not CONFIG.pwd:
        logger.error("未指定密钥.", popup=True)
        sys.exit()

    cipher = AESCipher(CONFIG.pwd)

    operation_name = {
        "encrypt": "加密",
        "decrypt": "解密",
    }.get(operation)

    processed_tags = []
    skipped_tags = []
    failed_tags = []

    for tag in CONFIG.tags:
        success, reason = _process_tag(tag, operation, cipher)
        if success:
            processed_tags.append(tag)
        elif reason == "已加密":
            skipped_tags.append(tag)
        else:
            failed_tags.append((tag, reason))

    # 生成消息
    if failed_tags:
        msg = f"以下标签操作失败: {failed_tags}"
    elif skipped_tags and not processed_tags:
        msg = f"以下标签已加密，跳过: {skipped_tags}"
    elif not processed_tags:
        msg = f"所有标签均已{operation_name}"
    else:
        msg = f"本次{operation_name}的标签 -> {processed_tags}."
        if skipped_tags:
            msg += f" (已跳过: {skipped_tags})"

    logger.info(msg, popup=True)


def process_single_tag(tag: str, operation: str) -> None:
    """处理指定标签的加密/解密操作"""
    if not CONFIG.pwd:
        logger.error("未指定密钥.", popup=True)
        sys.exit()

    # 验证标签
    if tag != CONFIG.default and tag not in CONFIG.tags:
        logger.error(f"标签 '{tag}' 未注册.", popup=True)
        sys.exit()

    cipher = AESCipher(CONFIG.pwd)
    success, reason = _process_tag(tag, operation, cipher)

    if success:
        op_name = "加密" if operation == "encrypt" else "解密"
        logger.info(f"标签 '{tag}' {op_name}成功.", popup=True)
    else:
        if reason == "已加密":
            logger.warning(f"标签 '{tag}' 已加密，跳过.", popup=True)
        else:
            logger.error(f"标签 '{tag}' 操作失败: {reason}", popup=True)


def validate_tag(tag: str) -> str:
    """标签检查"""
    if tag == CONFIG.default:
        return tag

    if tag not in CONFIG.tags:
        logger.warning(f"未注册的标签: {tag}")
        return CONFIG.default

    if not search_file_in_dirs(CONFIG.path, tag):
        logger.warning(f"标签文件缺失 {tag}")
        return CONFIG.default
    return tag


def check_configs() -> bool:
    """配置文件初始化检查"""
    try:
        CONFIG.tag = check_argument()
        client = CONFIG.client
        path = CONFIG.path
        default_tdata = CONFIG.default

        if not os.path.isfile(os.path.join(path, client)):
            raise TASConfigException("无法找到客户端")

        if not os.path.isdir(path):
            raise TASConfigException("路径格式不正确")

        if not default_tdata:
            raise TASConfigException("默认的账户未设置")

        if not search_file_in_dirs(path, default_tdata):
            raise TASConfigException(
                f"默认账户配置无效, 标记为'{default_tdata}'的账户文件夹未找到"
            )

        return True
    except TASConfigException as e:
        logger.error(f"配置验证失败, {e.message}.", popup=True)
        return False
    except Exception as e:
        raise e


async def status_handler(is_alive: bool) -> None:
    """监控回调"""
    CONFIG.process_status = is_alive


def run_async_in_thread(loop, coro) -> None:
    """启动后台监视器线程"""
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


async def watcher(monitor) -> None:
    """后台进程监控器"""
    monitor.add_callback(status_handler)
    await monitor.start_watching()
    while True:
        if CONFIG.complete:
            await monitor.stop_watching()
            break
        await asyncio.sleep(1)


def initialize() -> bool:
    """初始化函数"""
    register_signal_handlers()
    atexit.register(log_and_exit)
    sys.excepthook = handle_global_exception
    config_file = CONFIG.config_file
    if not os.path.exists(config_file):
        logger.error(f"配置文件 {config_file} 不存在.")
        open_settings_window(VERSION)
        sys.exit()
    else:
        try:
            if not check_configs():
                open_settings_window(VERSION)
                sys.exit()
        except Exception as e:
            logger.exception(
                "客户端初始化失败, 请重试.\n若问题依旧请联系开发者或发布Issues.",
                e,
                popup=True,
            )
            sys.exit()
    logger.info("初始化成功.")
    return True


def main():
    """主函数"""
    initialize()
    ProcessManager.kill_process(CONFIG.client)

    if CONFIG.tag:
        loop = asyncio.new_event_loop()
        monitor = ProcessMonitor(CONFIG.client)
        watch_thread = threading.Thread(target=run_async_in_thread, args=(loop, watcher(monitor)), daemon=True)
        watch_thread.start()
        logger.info("监控线程启动成功.")

    AccountSwitcher().process()
    CONFIG.complete = True

    return 0
