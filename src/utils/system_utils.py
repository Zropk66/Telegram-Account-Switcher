# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import socket
import sys
import traceback


def handle_global_exception(exc_type, exc_value, exc_traceback):
    """捕获全局未处理错误"""
    from src.utils import Logger
    logger = Logger()
    if exc_type is KeyboardInterrupt or exc_type is SystemExit:
        logger.info("捕捉到退出命令.")
        sys.exit(0)
    error_message = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.critical(f"捕获的未处理异常: \n{error_message}")


def check_lock(port):
    """绑定端口"""
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        lock_socket.bind(('0.0.0.0', port))
        lock_socket.listen()
        return lock_socket
    except socket.error:
        return False


def format_timedelta(delta):
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}时{minutes}分{seconds}秒"
