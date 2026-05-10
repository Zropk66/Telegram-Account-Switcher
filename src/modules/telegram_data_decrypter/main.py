# -*- coding: utf-8 -*-
import hashlib
import os
from io import BytesIO

import src.modules.telegram_data_decrypter.file_io as file_io
import src.modules.telegram_data_decrypter.settings as settings
import src.modules.telegram_data_decrypter.storage as storage
from src.modules.telegram_data_decrypter.qt import read_qt_int32, read_qt_uint64

DEFAULT_DATANAME = 'data'


def _file_key_to_str(file_key: bytes) -> str:
    return ''.join(f'{b:X}'[::-1] for b in file_key)


def _compute_data_name_key(dataname: str) -> str:
    file_key = hashlib.md5(dataname.encode('utf8')).digest()[:8]
    return _file_key_to_str(file_key)


def _compose_account_name(dataname: str, index: int) -> str:
    return f'{dataname}#{index + 1}' if index > 0 else dataname


def _read_mtp_authorization_user_id(data: BytesIO) -> int:
    legacy_user_id = read_qt_int32(data)
    legacy_main_dc_id = read_qt_int32(data)

    if legacy_user_id == -1 and legacy_main_dc_id == -1:
        return read_qt_uint64(data)
    return legacy_user_id


def decrypt_accounts(tdata_path, passcode=None):
    base_path = str(tdata_path)
    key_data_path = os.path.join(base_path, f'key_{DEFAULT_DATANAME}')
    key_data_tdf = file_io.read_tdf_file(key_data_path)

    passcode_bytes = (passcode or '').encode()
    local_key, account_indexes_data = storage.decrypt_key_data_tdf(passcode_bytes, key_data_tdf)
    account_indexes, _ = storage.read_key_data_accounts(BytesIO(account_indexes_data))

    accounts = []
    for index in account_indexes:
        dataname_key = _compute_data_name_key(_compose_account_name(DEFAULT_DATANAME, index))
        account_file_path = os.path.join(base_path, dataname_key)
        version, encrypted_data = file_io.read_encrypted_file(account_file_path, local_key)

        blocks = settings.read_settings_blocks(version, BytesIO(encrypted_data))
        mtp_authorization = blocks[settings.SettingsBlocks.dbiMtpAuthorization]
        user_id = _read_mtp_authorization_user_id(BytesIO(mtp_authorization))

        accounts.append({
            'index': index,
            'user_id': user_id,
        })

    return accounts
