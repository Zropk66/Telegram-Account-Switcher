# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import sys


def handle_global_exception(exc_type, exc_value, exc_traceback):
    """捕获全局未处理错误"""
    from src.utils import Logger
    logger = Logger()
    if exc_type is KeyboardInterrupt or exc_type is SystemExit:
        logger.info("捕捉到退出命令.")
        sys.exit(0)
    logger.exception(f"捕获的未处理异常, 请尝试重启程序,\n若问题依旧请联系开发者或发布Issues，开发者会尽快解决该问题:", exc_value, popup=True)


def format_timedelta(delta):
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}时{minutes}分{seconds}秒"
