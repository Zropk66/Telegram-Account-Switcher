"""Qt 二进制数据格式读取工具。

Telegram 桌面端使用 Qt 的序列化格式来存储本地数据，
本模块提供从字节流中读取整数、字节数组和 UTF-16 字符串的基础方法。
"""

from io import BytesIO


def _read_bytes(data: BytesIO, size: int) -> bytes:
    """从字节流中精确读取指定长度的字节，数据不足时抛出 StopIteration。"""
    b = data.read(size)
    if len(b) != size:
        raise StopIteration()

    return b


def read_qt_integer(data: BytesIO, size: int, signed: bool) -> int:
    """从字节流中读取大端序整数，可指定字节数和是否有符号。"""
    return int.from_bytes(_read_bytes(data, size), 'big', signed=signed)


def read_qt_int32(data: BytesIO) -> int:
    """读取 32 位有符号整数。"""
    return read_qt_integer(data, 4, True)


def read_qt_uint32(data: BytesIO) -> int:
    """读取 32 位无符号整数。"""
    return read_qt_integer(data, 4, False)


def read_qt_int64(data: BytesIO) -> int:
    """读取 64 位有符号整数。"""
    return read_qt_integer(data, 8, True)


def read_qt_uint64(data: BytesIO) -> int:
    """读取 64 位无符号整数。"""
    return read_qt_integer(data, 8, False)


def read_qt_byte_array(data: BytesIO) -> bytes:
    """读取 Qt 格式的字节数组（前 4 字节为 int32 长度，后跟对应长度的原始字节）。"""
    length = read_qt_int32(data)
    if length <= 0:
        return b''

    return _read_bytes(data, length)


def read_qt_utf8(data: BytesIO) -> str:
    """读取 Qt 格式的 UTF-16 字符串（按字节数组读取后用 UTF-16 解码）。"""
    return read_qt_byte_array(data).decode('utf16')
