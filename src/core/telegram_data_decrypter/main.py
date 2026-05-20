"""
Telegram 账户解密主逻辑。

本模块负责从 tdata 目录解析加密的存储文件，通过密码派生密钥，
最终从 MTP 授权结构中提取用户 ID。
"""
import hashlib
import os
from io import BytesIO

from src.core.telegram_data_decrypter import file_io, settings, storage
from src.core.telegram_data_decrypter.qt import read_qt_int32, read_qt_uint64

# Telegram 内部数据文件名
DEFAULT_DATANAME = 'data'


def _compute_data_name_key(dataname: str) -> str:
    """计算 Telegram 内部数据文件名的十六进制映射键。"""
    # 算法：MD5(dataname)[:8] 字节序反转
    file_key = hashlib.md5(dataname.encode('utf8')).digest()[:8]
    return ''.join(f'{b:X}'[::-1] for b in file_key)


def _compose_account_name(dataname: str, index: int) -> str:
    """生成账户数据名。首个账户为 data，后续为 data#2, data#3 等。"""
    return f'{dataname}#{index + 1}' if index > 0 else dataname


def _read_mtp_authorization_user_id(data: BytesIO) -> int:
    """
    从解密后的 MTP 数据块中提取 UserID。
    """
    legacy_user_id = read_qt_int32(data)
    legacy_main_dc_id = read_qt_int32(data)

    # 如果前缀为 -1, -1，说明是新格式，ID 存储为 uint64
    if legacy_user_id == -1 and legacy_main_dc_id == -1:
        return read_qt_uint64(data)
    return legacy_user_id


def decrypt_accounts(tdata_path: str, passcode: str = None) -> list:
    """
    遍历并解密 tdata 目录下的所有 Telegram 账户。
    """
    base_path = str(tdata_path)
    key_data_path = os.path.join(base_path, f'key_{DEFAULT_DATANAME}')
    key_data_tdf = file_io.read_tdf_file(key_data_path)

    # 1. 解密主密钥
    passcode_bytes = (passcode or '').encode()
    local_key, account_indexes_data = storage.decrypt_key_data_tdf(passcode_bytes, key_data_tdf)
    account_indexes, _ = storage.read_key_data_accounts(BytesIO(account_indexes_data))

    accounts = []
    for index in account_indexes:
        # 2. 定位并读取每个账户的数据文件
        dataname_key = _compute_data_name_key(_compose_account_name(DEFAULT_DATANAME, index))
        account_file_path = os.path.join(base_path, dataname_key)
        version, encrypted_data = file_io.read_encrypted_file(account_file_path, local_key)

        # 3. 解析账户数据块并提取 UserID
        blocks = settings.read_settings_blocks(version, BytesIO(encrypted_data))
        mtp_authorization = blocks[settings.SettingsBlocks.dbiMtpAuthorization]
        user_id = _read_mtp_authorization_user_id(BytesIO(mtp_authorization))

        accounts.append({
            'index': index,
            'user_id': user_id,
        })

    return accounts
