"""密钥数据文件的解密与账户索引读取。

Telegram 在 tdata 目录下存储一个 key_data 文件，
其中包含用于解密各账户数据文件的 local_key，
以及所有已登录账户的索引列表。
本模块负责解密这个密钥文件并提取账户信息。
"""

from io import BytesIO
from typing import Tuple, List

from src.core.telegram_data_decrypter.crypto import create_local_key, decrypt_local
from src.core.telegram_data_decrypter.qt import read_qt_byte_array, read_qt_int32
from src.core.telegram_data_decrypter.tdf import RawTdfFile


def decrypt_key_data_tdf(passcode: bytes, key_data_tdf: RawTdfFile):
    """解密 key_data TDF 文件，用 passcode 派生密钥解密 local_key，再用 local_key 解密账户索引信息，返回 (local_key, info_decrypted)。"""
    stream = BytesIO(key_data_tdf.encrypted_data)

    salt = read_qt_byte_array(stream)
    key_encrypted = read_qt_byte_array(stream)
    info_encrypted = read_qt_byte_array(stream)

    # 第一层：用 passcode 派生的密钥解密 local_key
    passcode_key = create_local_key(passcode, salt)
    local_key = decrypt_local(key_encrypted, passcode_key)

    # 第二层：用 local_key 解密账户索引信息
    info_decrypted = decrypt_local(info_encrypted, local_key)
    return local_key, info_decrypted


def read_key_data_accounts(data: BytesIO) -> Tuple[List[int], int]:
    """从解密后的 key_data 中读取账户索引列表和主账户索引，返回 (indexes, main_account)。"""
    count = read_qt_int32(data)

    indexes = [
        read_qt_int32(data)
        for _ in range(count)
    ]

    main_account = read_qt_int32(data)

    return indexes, main_account
