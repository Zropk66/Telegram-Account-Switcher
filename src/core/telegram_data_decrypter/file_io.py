"""
TDF 文件处理模块。

负责从磁盘读取 Telegram 的 TDF (Telegram Data File) 格式文件，
并解析其中的加密载荷。
"""
from io import BytesIO
from typing import Tuple

from src.core.telegram_data_decrypter.crypto import decrypt_local
from src.core.telegram_data_decrypter.qt import read_qt_byte_array
from src.core.telegram_data_decrypter.tdf import RawTdfFile, parse_raw_tdf


def read_tdf_file(filepath: str) -> RawTdfFile:
    """
    读取并解析原始 TDF 文件。

    注：TDF 路径在程序中通常不带 's'，但磁盘文件名带有 's' 后缀，此处自动补全。
    """
    real_path = filepath + 's'
    with open(real_path, 'rb') as f:
        return parse_raw_tdf(f.read())


def read_encrypted_file(filepath: str, local_key: bytes) -> Tuple[int, bytes]:
    """
    读取指定 TDF 文件，执行 Qt 字节流解析并使用 local_key 进行解密。
    """
    tdf_file = read_tdf_file(filepath)
    # Telegram 将数据序列化为 Qt 字节数组格式
    encrypted_data = read_qt_byte_array(BytesIO(tdf_file.encrypted_data))
    return tdf_file.version, decrypt_local(encrypted_data, local_key)
