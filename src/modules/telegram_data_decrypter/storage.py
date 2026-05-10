from io import BytesIO
from typing import Tuple, List

from src.modules.telegram_data_decrypter.crypto import create_local_key, decrypt_local
from src.modules.telegram_data_decrypter.qt import read_qt_byte_array, read_qt_int32
from src.modules.telegram_data_decrypter.tdf import RawTdfFile


def decrypt_key_data_tdf(passcode: bytes, key_data_tdf: RawTdfFile):
    stream = BytesIO(key_data_tdf.encrypted_data)

    salt = read_qt_byte_array(stream)
    key_encrypted = read_qt_byte_array(stream)
    info_encrypted = read_qt_byte_array(stream)

    passcode_key = create_local_key(passcode, salt)
    local_key = decrypt_local(key_encrypted, passcode_key)

    info_decrypted = decrypt_local(info_encrypted, local_key)
    return local_key, info_decrypted


def read_key_data_accounts(data: BytesIO) -> Tuple[List[int], int]:
    count = read_qt_int32(data)

    indexes = [
        read_qt_int32(data)
        for _ in range(count)
    ]

    main_account = read_qt_int32(data)

    return indexes, main_account
