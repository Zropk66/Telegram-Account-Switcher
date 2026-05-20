"""
Qt 二进制序列化工具。

Telegram 本地数据采用 Qt 的二进制格式存储，本模块提供
针对此类数据流（big-endian 整数、带长度前缀的字节数组）的解析能力。
"""
from io import BytesIO


def _read_exact(data: BytesIO, size: int) -> bytes:
    """从流中读取固定长度字节，不足时触发异常。"""
    b = data.read(size)
    if len(b) != size:
        raise StopIteration("字节流数据不足")
    return b


def _read_int(data: BytesIO, size: int, signed: bool) -> int:
    """读取大端序整数。"""
    return int.from_bytes(_read_exact(data, size), 'big', signed=signed)


def read_qt_int32(data: BytesIO) -> int:
    """读取 32 位有符号整数。"""
    return _read_int(data, 4, True)


def read_qt_uint32(data: BytesIO) -> int:
    """读取 32 位无符号整数。"""
    return _read_int(data, 4, False)


def read_qt_int64(data: BytesIO) -> int:
    """读取 64 位有符号整数。"""
    return _read_int(data, 8, True)


def read_qt_uint64(data: BytesIO) -> int:
    """读取 64 位无符号整数。"""
    return _read_int(data, 8, False)


def read_qt_byte_array(data: BytesIO) -> bytes:
    """
    读取 Qt 字节数组格式：[int32 长度][raw 数据]。
    """
    length = read_qt_int32(data)
    return _read_exact(data, length) if length > 0 else b''


def read_qt_utf8(data: BytesIO) -> str:
    """读取 Qt 格式的字符串（底层实际为 UTF-16 编码）。"""
    return read_qt_byte_array(data).decode('utf-16')
