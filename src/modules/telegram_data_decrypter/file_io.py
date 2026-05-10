from io import BytesIO
from typing import Tuple

from src.modules.telegram_data_decrypter.crypto import decrypt_local
from src.modules.telegram_data_decrypter.qt import read_qt_byte_array
from src.modules.telegram_data_decrypter.tdf import RawTdfFile, parse_raw_tdf


def read_tdf_file(filepath: str) -> RawTdfFile:
    real_path = filepath + 's'
    try:
        with open(real_path, 'rb') as f:
            return parse_raw_tdf(f.read())
    except FileNotFoundError as e:
        raise FileNotFoundError(real_path) from e


def read_encrypted_file(filepath: str, local_key: bytes) -> Tuple[int, bytes]:
    tdf_file = read_tdf_file(filepath)
    encrypted_data = read_qt_byte_array(BytesIO(tdf_file.encrypted_data))
    return tdf_file.version, decrypt_local(encrypted_data, local_key)
