"""自定义异常定义."""


class TASException(Exception):  # noqa: N818
    """业务逻辑异常基类."""

    pass


class TASConfigException(TASException):
    """配置相关异常."""

    pass


class TASCipherException(TASException):
    """加解密异常."""

    pass


class SingleInstanceException(TASException):
    """单实例运行异常."""

    pass
