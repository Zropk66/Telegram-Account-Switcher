class TASException(Exception):
    """TAS 通用异常基类。"""

    def __init__(self, message='TAS EXCEPTION'):
        self.message = message

    def __str__(self):
        return self.message


class TASConfigException(TASException):
    """配置校验失败时抛出。"""

    def __init__(self, message='TAS CONFIG EXCEPTION'):
        self.message = message


class TASCipherException(TASException):
    """加解密过程中出现错误时抛出。"""

    def __init__(self, message='TAS CIPHER EXCEPTION'):
        self.message = message
