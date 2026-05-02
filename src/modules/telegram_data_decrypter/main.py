# -*- coding: utf-8 -*-
# @File    : main.py
# @Time    : 2026/2/18 20:55
# @Author  : Zropk
import os
import pathlib
from io import BytesIO

import src.modules.telegram_data_decrypter.file_io as file_io
import src.modules.telegram_data_decrypter.settings as settings
import src.modules.telegram_data_decrypter.storage as storage
from src.modules.telegram_data_decrypter.decrypter import TdataReader, compose_account_name, compute_data_name_key, read_mtp_authorization



def decrypt_accounts(tdata_path, passcode=None):
    base_path = str(tdata_path)
    dataname = TdataReader.DEFAULT_DATANAME

    key_data_name = 'key_' + dataname
    key_data_path = os.path.join(base_path, key_data_name)
    key_data_tdf = file_io.read_tdf_file(key_data_path)

    passcode_bytes = (passcode or '').encode()
    local_key, account_indexes_data = storage.decrypt_key_data_tdf(passcode_bytes, key_data_tdf)
    account_indexes, _ = storage.read_key_data_accounts(BytesIO(account_indexes_data))

    accounts = []
    for index in account_indexes:
        account_name = compose_account_name(dataname, index)
        dataname_key = compute_data_name_key(account_name)

        account_file_path = os.path.join(base_path, dataname_key)
        version, encrypted_data = file_io.read_encrypted_file(account_file_path, local_key)

        blocks = settings.read_settings_blocks(version, BytesIO(encrypted_data))
        mtp_authorization = blocks[settings.SettingsBlocks.dbiMtpAuthorization]
        mtp_data = read_mtp_authorization(BytesIO(mtp_authorization))

        accounts.append({
            'index': index,
            'user_id': mtp_data.user_id,
        })

    return accounts

def get_account_ids(base_path, passcode=None):
    base_path = pathlib.Path(base_path)

    tdatas = {}

    for folder in base_path.iterdir():
        path = base_path.joinpath(folder)
        if not path.is_dir() or not path.joinpath('key_datas').exists():
            continue
        accounts = decrypt_accounts(path, passcode)
        if not tdatas.get(accounts[0].get('user_id')):
            tdatas[accounts[0].get('user_id')] = str(folder)
    return tdatas