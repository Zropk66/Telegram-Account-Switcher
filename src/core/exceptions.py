"""
项目自定义异常定义。

提供统一的错误类型体系，方便在业务层进行精细化的异常捕获和用户反馈。
"""


class TASException(Exception):
    """业务逻辑异常基类。"""

    def __init__(self, message='TAS EXCEPTION'):
        """初始化。"""
        self.message = message

    def __str__(self):
        """内部方法：__str__。"""
        return self.message


class TASConfigException(TASException):
    """配置相关异常。"""

    def __init__(self, message='TAS CONFIG EXCEPTION'):
        """初始化。"""
        super().__init__(message)


class TASCipherException(TASException):
    """加解密异常。"""

    def __init__(self, message='TAS CIPHER EXCEPTION'):
        """初始化。"""
        super().__init__(message)

class SingleInstanceException(TASException):
    """无法获取单实例锁时抛出。"""
    pass