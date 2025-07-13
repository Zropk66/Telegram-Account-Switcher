# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
class TASException(Exception):
    """程序异常类"""
    def __init__(self, message='TAS ERROR'):
        self.message = message

    def __str__(self):
        return self.message

class TASConfigException(TASException):
    """配置检查异常类"""
    def __init__(self, message='TAS CONFIG ERROR'):
        self.message = message

