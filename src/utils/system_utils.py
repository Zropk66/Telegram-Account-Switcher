# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import socket
import sys
import traceback

def handle_global_exception(self, exc_type, exc_value, exc_traceback):
    """捕获全局未处理错误"""
    if exc_type is KeyboardInterrupt:
        self.logger.info("捕捉退出命令.")
        sys.exit(0)
    errorMessage = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    self.logger.critical(f"捕获的未处理异常: \n{errorMessage}")

def bind_singleton(port):
    """绑定端口"""
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        lock_socket.bind(('0.0.0.0', port))
        lock_socket.listen()
        return lock_socket
    except socket.error:
        return False