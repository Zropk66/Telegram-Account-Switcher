# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
class TASException(Exception):
    """程序异常类"""

    def __init__(self, message='TAS EXCEPTION'):
        self.message = message

    def __str__(self):
        return self.message


class TASConfigException(TASException):
    """配置检查异常类"""

    def __init__(self, message='TAS CONFIG EXCEPTION'):
        self.message = message


class TASCipherException(TASException):
    """加解密异常类"""

    def __init__(self, message='TAS CIPHER EXCEPTION'):
        self.message = message
