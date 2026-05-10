"""TDF 文件读取与解密入口模块。

负责从磁盘读取 Telegram 的 TDF 格式文件，
解析其中的加密数据并用本地密钥进行解密。
"""

from io import BytesIO
from typing import Tuple

from src.core.telegram_data_decrypter.crypto import decrypt_local
from src.core.telegram_data_decrypter.qt import read_qt_byte_array
from src.core.telegram_data_decrypter.tdf import RawTdfFile, parse_raw_tdf


def read_tdf_file(filepath: str) -> RawTdfFile:
    """读取 filepath 自动补 's' 后缀的 TDF 文件并解析为 RawTdfFile 对象。"""
    real_path = filepath + 's'
    try:
        with open(real_path, 'rb') as f:
            return parse_raw_tdf(f.read())
    except FileNotFoundError as e:
        raise FileNotFoundError(real_path) from e


def read_encrypted_file(filepath: str, local_key: bytes) -> Tuple[int, bytes]:
    """读取 TDF 文件并用 local_key 解密其中的数据，返回 (version, decrypted_data) 元组。"""
    tdf_file = read_tdf_file(filepath)
    encrypted_data = read_qt_byte_array(BytesIO(tdf_file.encrypted_data))
    return tdf_file.version, decrypt_local(encrypted_data, local_key)
