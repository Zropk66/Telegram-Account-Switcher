"""
key_data 存储解析。

Telegram 的 `key_data` 文件包含了解密所有其他账户数据文件的“根密钥”
以及已登录账户的索引列表。本模块负责两层解密逻辑及索引解析。
"""
from io import BytesIO
from typing import Tuple, List

from src.core.telegram_data_decrypter.crypto import create_local_key, decrypt_local
from src.core.telegram_data_decrypter.qt import read_qt_byte_array, read_qt_int32
from src.core.telegram_data_decrypter.tdf import RawTdfFile


def decrypt_key_data_tdf(passcode: bytes, key_data_tdf: RawTdfFile) -> Tuple[bytes, bytes]:
    """
    执行两层解密流程：
    1. 使用 passcode 和盐派生第一层密钥，解密得到真正的根密钥 (local_key)。
    2. 使用根密钥解密账户列表索引数据。
    """
    stream = BytesIO(key_data_tdf.encrypted_data)

    salt = read_qt_byte_array(stream)
    key_encrypted = read_qt_byte_array(stream)
    info_encrypted = read_qt_byte_array(stream)

    # 1. 解密根密钥
    passcode_key = create_local_key(passcode, salt)
    local_key = decrypt_local(key_encrypted, passcode_key)

    # 2. 解密账户索引信息
    info_decrypted = decrypt_local(info_encrypted, local_key)
    return local_key, info_decrypted


def read_key_data_accounts(data: BytesIO) -> Tuple[List[int], int]:
    """
    解析已解密的账户列表数据流。

    结构: [int32: 计数][int32[]: 索引列表][int32: 主账户索引]
    """
    count = read_qt_int32(data)
    indexes = [read_qt_int32(data) for _ in range(count)]
    main_account = read_qt_int32(data)

    return indexes, main_account
