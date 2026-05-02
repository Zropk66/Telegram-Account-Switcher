# -*- coding: utf-8 -*-
import argparse
import asyncio
import atexit
import signal
import sys
import threading
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


def log_and_exit(mark=False):
    """程序退出清理"""
    with suppress(Exception):
        if mark:
            atexit.unregister(log_and_exit)
            recovery()

        if CONFIG.log_output and getattr(CONFIG, "_start_time", None):
            logger.info(f"监控时长：{CONFIG.watch_time()}")
    return None


def register_signal_handlers():
    """注册信号监听"""

    def handle_interrupt(signum, frame):
        log_and_exit(True)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_interrupt)


def handle_global_exception(exc_type, exc_value, exc_traceback):
    """全局异常捕获"""
    if exc_type in (KeyboardInterrupt, SystemExit):
        sys.exit(0)
    logger.exception(
        "捕获到未处理异常, 请尝试重启程序或联系开发者.",
        exc_value,
        popup=True,
    )


def parse_arguments() -> argparse.Namespace:
    """CLI 参数解析"""
    parser = argparse.ArgumentParser(description="TAS CLI", add_help=False, exit_on_error=False)

    action_group = parser.add_argument_group()
    action_group.add_argument("--encrypt", "-e", action="store_true", help="加密账户")
    action_group.add_argument("--decrypt", "-d", action="store_true", help="解密账户")
    action_group.add_argument("--switch", "-s", type=str, metavar="tag", help="切换至指定标签账户")
    action_group.add_argument("--key-login", "-k", action="store_true", help="强制Key登录")
    action_group.add_argument("--tag", "-t", type=str, metavar="tag", help="操作指定标签")

    exclusive_group = parser.add_mutually_exclusive_group()
    exclusive_group.add_argument("--version", "-v", action="store_true", help="查看版本")
    exclusive_group.add_argument("--settings", "-c", action="store_true", help="打开设置")
    exclusive_group.add_argument("--help", "-h", action="store_true", help="查看帮助")
    parser.add_argument("--password", "-p", type=str, metavar="password", help="指定解密密钥")

    return parser.parse_args()


def check_argument(args: argparse.Namespace) -> str | None:
    """校验命令行参数"""
    if args.password:
        CONFIG.pwd = args.password

    if args.key_login:
        CONFIG.force_key_login = True

    if args.switch:
        return validate_tag(args.switch)

    return None


def handle_cli_actions(args: argparse.Namespace) -> bool:
    """执行 CLI 相关动作"""
    if args.help:
        open_help_window(VERSION)
    elif args.version:
        logger.info(f"{TITLE} v{VERSION}", popup=True)
    elif args.settings:
        open_settings_window(VERSION)
    else:
        if args.encrypt:
            process_single_tag(args.tag, "encrypt") if args.tag else process_tags("encrypt")
        elif args.decrypt:
            process_single_tag(args.tag, "decrypt") if args.tag else process_tags("decrypt")
        else:
            return False
    return True


def _process_tag(tag: str, operation: str, cipher: AESCipher) -> tuple[bool, str | None]:
    """执行单个账户的加解密"""
    tag_path = search_file_in_dirs(CONFIG.path, tag)
    if not tag_path:
        return False, f"标签 '{tag}' 文件缺失"

    key_datas_path = Path(CONFIG.path) / tag_path / "key_datas"

    if not key_datas_path.exists():
        return False, "key_datas 文件不存在"

    try:
        if operation == "encrypt":
            if AESCipher.is_encrypted(key_datas_path):
                return False, "已加密"
            cipher.encrypt(key_datas_path)
            CONFIG.backup_account_keys(tag, key_datas_path.parent)
        else:
            cipher.decrypt(key_datas_path)
            CONFIG.backup_account_keys(tag, key_datas_path.parent)
        return True, None
    except Exception as e:
        return False, str(e)


def process_tags(operation: str) -> bool:
    """批量处理加解密"""
    if not CONFIG.pwd:
        logger.error("未指定密钥.", popup=True)
        sys.exit()

    cipher = AESCipher(CONFIG.pwd)
    op_name = "加密" if operation == "encrypt" else "解密"

    processed, skipped, failed = [], [], []

    for tag in CONFIG.tags:
        if tag == CONFIG.default:
            skipped.append(tag)
            continue

        success, reason = _process_tag(tag, operation, cipher)
        if success:
            processed.append(tag)
        elif reason == "已加密":
            skipped.append(tag)
        else:
            failed.append((tag, reason))

    if failed:
        msg = f"操作失败: {failed}"
    elif skipped and not processed:
        msg = f"标签均已{op_name}，跳过: {skipped}"
    elif not processed:
        msg = f"所有标签均已{op_name}"
    else:
        msg = f"本次{op_name}的标签 -> {processed}"
        if skipped:
            msg += f" (已跳过: {skipped})"

    logger.info(msg, popup=True)
    return True


def process_single_tag(tag: str, operation: str) -> bool | None:
    """处理指定账户的加解密"""
    if not CONFIG.pwd:
        logger.error("未指定密钥.", popup=True)
        sys.exit()

    if tag not in CONFIG.tags and tag != CONFIG.default:
        logger.error(f"标签 '{tag}' 未注册.", popup=True)
        sys.exit()

    if tag == CONFIG.default:
        logger.warning(f"标签 '{tag}' 为默认账户，禁止操作。", popup=True)
        return False

    cipher = AESCipher(CONFIG.pwd)
    success, reason = _process_tag(tag, operation, cipher)

    if success:
        logger.info(f"标签 '{tag}' {'加密' if operation == 'encrypt' else '解密'}成功", popup=True)
        return True
    else:
        if reason == "已加密":
            logger.warning(f"标签 '{tag}' 已加密，跳过.", popup=True)
        else:
            logger.error(f"标签 '{tag}' 操作失败: {reason}", popup=True)


def validate_tag(tag: str) -> str:
    """校验标签合法性"""
    if tag == CONFIG.default:
        return tag

    if tag not in CONFIG.tags or not search_file_in_dirs(CONFIG.path, tag):
        logger.warning(f"标签无效或文件缺失: {tag}")
        return CONFIG.default
    return tag


def check_configs(args: argparse.Namespace) -> bool:
    """启动前配置检查"""
    try:
        # 先尝试同步路径，增强健壮性
        CONFIG.sync_all_account_paths()
        
        CONFIG.tag = check_argument(args)
        path = Path(CONFIG.path)

        if not (path / CONFIG.client).is_file():
            raise TASConfigException("找不到客户端程序")
        if not path.is_dir():
            raise TASConfigException("路径格式不正确")
        if not CONFIG.default:
            raise TASConfigException("未设置默认账户")
        if not search_file_in_dirs(str(path), CONFIG.default):
            raise TASConfigException(f"默认账户 '{CONFIG.default}' 文件夹未找到")

        return True
    except TASConfigException as e:
        logger.error(f"配置验证失败: {e.message}", popup=True)
        return False
    except Exception as e:
        logger.exception("验证配置时发生异常", e)
        return False


async def status_handler(is_alive: bool) -> None:
    CONFIG.process_status = is_alive


def run_async_in_thread(loop, coro) -> None:
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


async def watcher(monitor) -> None:
    """运行进程健康监控"""
    monitor.add_callback(status_handler)
    await monitor.start_watching()
    while not CONFIG.complete:
        await asyncio.sleep(1)
    await monitor.stop_watching()


def main():
    """主入口"""
    register_signal_handlers()
    sys.excepthook = handle_global_exception
    atexit.register(log_and_exit)

    try:
        args = parse_arguments()
    except Exception:
        return 0

    config_file = Path(CONFIG.config_file)
    if not config_file.exists() or not check_configs(args):
        open_settings_window(VERSION)
        return 0

    if handle_cli_actions(args):
        return 0

    logger.info("初始化成功")

    # 启动监控
    loop = asyncio.new_event_loop()
    monitor = ProcessMonitor(CONFIG.client)
    threading.Thread(target=run_async_in_thread, args=(loop, watcher(monitor)), daemon=True).start()
    logger.info("监控线程启动成功")

    # 关闭存留进程并执行切换
    ProcessManager.kill_process(CONFIG.client)
    AccountSwitcher().process()

    CONFIG.complete = True
    return 0
