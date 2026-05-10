"""Telegram 账户解密主入口。

从 tdata 目录中读取所有已登录账户的信息，
解密密钥文件和各账户的数据文件，提取出每个账户的用户 ID。
"""

import hashlib
import os
from io import BytesIO

import src.core.telegram_data_decrypter.file_io as file_io
import src.core.telegram_data_decrypter.settings as settings
import src.core.telegram_data_decrypter.storage as storage
from src.core.telegram_data_decrypter.qt import read_qt_int32, read_qt_uint64

# Telegram 默认的数据文件名
DEFAULT_DATANAME = 'data'


# -- 辅助函数 --

def _file_key_to_str(file_key: bytes) -> str:
    """将 8 字节的文件标识转换为十六进制字符串（字节序反转）。

    Telegram 用 MD5 哈希的前 8 字节作为文件名，存储时做了字节序反转。
    """
    return ''.join(f'{b:X}'[::-1] for b in file_key)


def _compute_data_name_key(dataname: str) -> str:
    """对 dataname 做 MD5 取前 8 字节并反转字节序，返回用于在 tdata 目录中定位文件的大写十六进制文件名。"""
    file_key = hashlib.md5(dataname.encode('utf8')).digest()[:8]
    return _file_key_to_str(file_key)


def _compose_account_name(dataname: str, index: int) -> str:
    """拼接账户的数据名称，第一个账户直接用 dataname，后续账户加序号后缀如 'data#2'。"""
    return f'{dataname}#{index + 1}' if index > 0 else dataname


def _read_mtp_authorization_user_id(data: BytesIO) -> int:
    """从 MTP 授权数据块中读取用户 ID，新版格式（user_id 和 main_dc_id 均为 -1）时读取后续 uint64。"""
    legacy_user_id = read_qt_int32(data)
    legacy_main_dc_id = read_qt_int32(data)

    # 两个 -1 表示新版格式，后面跟着 uint64 的真实 user_id
    if legacy_user_id == -1 and legacy_main_dc_id == -1:
        return read_qt_uint64(data)
    return legacy_user_id


# -- 核心逻辑 --

def decrypt_accounts(tdata_path, passcode=None):
    """解密 tdata_path 下所有已登录账户，用 passcode 派生密钥后逐个解密数据文件并提取用户 ID，返回账户信息列表。"""
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
