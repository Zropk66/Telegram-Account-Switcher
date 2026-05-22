"""Telegram数据解密与解析。"""

import hashlib
import os
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import tgcrypto

from src.core.constants import (
    LOCAL_ITER_NO_PWD,
    LOCAL_ITER_WITH_PWD,
    STRONG_ITER_COUNT,
    DEFAULT_DATANAME,
    TDF_MAGIC
)


class CryptoException(Exception):
    """密码学操作异常。"""
    pass


def _read_exact(data: BytesIO, size: int) -> bytes:
    """读取指定长度字节。"""
    b = data.read(size)
    if len(b) != size:
        raise StopIteration("字节流数据不足")
    return b


def _read_int(data: BytesIO, size: int, signed: bool) -> int:
    """读取整型数值。"""
    return int.from_bytes(_read_exact(data, size), 'big', signed=signed)


def read_qt_int32(data: BytesIO) -> int:
    """读取32位有符号整型。"""
    return _read_int(data, 4, True)


def read_qt_uint32(data: BytesIO) -> int:
    """读取32位无符号整型。"""
    return _read_int(data, 4, False)


def read_qt_int64(data: BytesIO) -> int:
    """读取64位有符号整型。"""
    return _read_int(data, 8, True)


def read_qt_uint64(data: BytesIO) -> int:
    """读取64位无符号整型。"""
    return _read_int(data, 8, False)


def read_qt_byte_array(data: BytesIO) -> bytes:
    """读取字节包装数组。"""
    length = read_qt_int32(data)
    return _read_exact(data, length) if length > 0 else b''


def read_qt_string(data: BytesIO) -> str:
    """读取字符串。"""
    return read_qt_byte_array(data).decode('utf-16')


def create_local_key(passcode: bytes, salt: bytes) -> bytes:
    """生成本地加密密钥。"""
    iterations = STRONG_ITER_COUNT if passcode else 1
    password = hashlib.sha512(salt + passcode + salt).digest()
    return hashlib.pbkdf2_hmac('sha512', password, salt, iterations, 256)


def create_legacy_local_key(passcode: bytes, salt: bytes) -> bytes:
    """生成旧版本地加密密钥。"""
    iterations = LOCAL_ITER_WITH_PWD if passcode else LOCAL_ITER_NO_PWD
    return hashlib.pbkdf2_hmac('sha1', passcode, salt, iterations, 256)


def prepare_aes_old_mtp(local_key: bytes, msg_key: bytes, send: bool = False) -> Tuple[bytes, bytes]:
    """派生AES加密密钥与初始化向量。"""
    x = 0 if send else 8
    key_part = lambda pos, size: local_key[pos:pos + size]

    dataA = msg_key + key_part(x, 32)
    dataB = key_part(x + 32, 16) + msg_key + key_part(x + 48, 16)
    dataC = key_part(x + 64, 32) + msg_key
    dataD = msg_key + key_part(x + 96, 32)

    sha1A = hashlib.sha1(dataA).digest()
    sha1B = hashlib.sha1(dataB).digest()
    sha1C = hashlib.sha1(dataC).digest()
    sha1D = hashlib.sha1(dataD).digest()

    key = sha1A[:8] + sha1B[8:20] + sha1C[4:16]
    iv = sha1A[8:20] + sha1B[:8] + sha1C[16:20] + sha1D[:8]
    return key, iv


def aes_decrypt_local(encrypted_data: bytes, msg_key: bytes, local_key: bytes) -> bytes:
    """解密本地数据块。"""
    aes_key, aes_iv = prepare_aes_old_mtp(local_key, msg_key)
    return tgcrypto.ige256_decrypt(encrypted_data, aes_key, aes_iv)


def decrypt_local(encrypted_msg: bytes, local_key: bytes) -> bytes:
    """解密并校验本地数据块。"""
    msg_key, encrypted_data = encrypted_msg[:16], encrypted_msg[16:]
    decrypted = aes_decrypt_local(encrypted_data, msg_key, local_key)

    if hashlib.sha1(decrypted).digest()[:16] != msg_key:
        raise CryptoException('密钥错误或数据已损坏')

    length = int.from_bytes(decrypted[:4], 'little')
    if length > len(decrypted):
        raise CryptoException(f'数据长度校验失败: {length}')
    return decrypted[4:length]


@dataclass
class RawTdfFile:
    """原始TDF文件数据。"""
    version: int
    encrypted_data: bytes


def parse_raw_tdf(raw_data: bytes) -> RawTdfFile:
    """解析原始TDF文件数据。"""
    if len(raw_data) < 28 or raw_data[:4] != TDF_MAGIC:
        raise CryptoException('不是合法的 TDF 文件格式（魔数不匹配或数据过短）')
    version = int.from_bytes(raw_data[4:8], 'little')
    encrypted_data = raw_data[8:-16]
    return RawTdfFile(version, encrypted_data)


def read_tdf_file(filepath: str) -> RawTdfFile:
    """读取并解析TDF文件。"""
    real_path = filepath + 's'
    with open(real_path, 'rb') as f:
        return parse_raw_tdf(f.read())


def read_encrypted_file(filepath: str, local_key: bytes) -> Tuple[int, bytes]:
    """读取并解密数据文件。"""
    tdf_file = read_tdf_file(filepath)
    encrypted_data = read_qt_byte_array(BytesIO(tdf_file.encrypted_data))
    return tdf_file.version, decrypt_local(encrypted_data, local_key)


class SettingsBlocks(Enum):
    """配置块标识符。"""
    dbiKey = 0x00
    dbiUser = 0x01
    dbiAutoStart = 0x06
    dbiStartMinimized = 0x07
    dbiSeenTrayTooltip = 0x0a
    dbiAutoUpdate = 0x0c
    dbiLastUpdateCheck = 0x0d
    dbiScalePercent = 0x0e
    dbiDefaultAttach = 0x11
    dbiSendToMenu = 0x1d
    dbiDialogLastPath = 0x23
    dbiRecentStickers = 0x26
    dbiMtpAuthorization = 0x4b
    dbiSessionSettings = 0x4d
    dbiLangPackKey = 0x4e
    dbiThemeKey = 0x54
    dbiTileBackground = 0x55
    dbiPowerSaving = 0x57
    dbiLanguagesKey = 0x5a
    dbiCacheSettings = 0x5c
    dbiApplicationSettings = 0x5e
    dbiFallbackProductionConfig = 0x60
    dbiBackgroundKey = 0x61
    dbiEncrypted = 444
    dbiVersion = 666


def read_boolean(data: BytesIO) -> bool:
    """读取布尔值。"""
    return read_qt_int32(data) == 1


def read_settings_block(version: int, data: BytesIO, block_id: SettingsBlocks) -> Any:
    """读取特定配置块。"""
    if block_id in (SettingsBlocks.dbiAutoStart, SettingsBlocks.dbiStartMinimized,
                    SettingsBlocks.dbiSendToMenu, SettingsBlocks.dbiSeenTrayTooltip,
                    SettingsBlocks.dbiAutoUpdate):
        return read_boolean(data)

    if block_id in (SettingsBlocks.dbiLastUpdateCheck, SettingsBlocks.dbiScalePercent,
                    SettingsBlocks.dbiPowerSaving):
        return read_qt_int32(data)

    if block_id in (SettingsBlocks.dbiFallbackProductionConfig,
                    SettingsBlocks.dbiApplicationSettings,
                    SettingsBlocks.dbiMtpAuthorization):
        return read_qt_byte_array(data)

    if block_id == SettingsBlocks.dbiDialogLastPath:
        return read_qt_string(data)

    if block_id == SettingsBlocks.dbiThemeKey:
        return {
            'day': read_qt_uint64(data),
            'night': read_qt_uint64(data),
            'night_mode': read_boolean(data)
        }

    if block_id == SettingsBlocks.dbiBackgroundKey:
        return {
            'day': read_qt_uint64(data),
            'night': read_qt_uint64(data)
        }

    if block_id == SettingsBlocks.dbiTileBackground:
        return {'day': read_qt_int32(data), 'night': read_qt_int32(data)}

    if block_id == SettingsBlocks.dbiLangPackKey:
        return read_qt_uint64(data)

    raise ValueError(f'未知 Block ID: {block_id}')


def read_settings_blocks(version: int, data: BytesIO) -> Dict[SettingsBlocks, Any]:
    """读取所有配置块。"""
    blocks = {}
    try:
        while True:
            block_id = SettingsBlocks(read_qt_int32(data))
            blocks[block_id] = read_settings_block(version, data, block_id)
    except StopIteration:
        pass
    return blocks


def decrypt_key_data_tdf(passcode: bytes, key_data_tdf: RawTdfFile) -> Tuple[bytes, bytes]:
    """解密主密钥文件数据。"""
    stream = BytesIO(key_data_tdf.encrypted_data)

    salt = read_qt_byte_array(stream)
    key_encrypted = read_qt_byte_array(stream)
    info_encrypted = read_qt_byte_array(stream)

    passcode_key = create_local_key(passcode, salt)
    try:
        local_key = decrypt_local(key_encrypted, passcode_key)
    except CryptoException:
        passcode_key_legacy = create_legacy_local_key(passcode, salt)
        local_key = decrypt_local(key_encrypted, passcode_key_legacy)

    info_decrypted = decrypt_local(info_encrypted, local_key)
    return local_key, info_decrypted


def read_key_data_accounts(data: BytesIO) -> Tuple[List[int], int]:
    """读取账户索引与主账户标识。"""
    count = read_qt_int32(data)
    indexes = [read_qt_int32(data) for _ in range(count)]
    main_account = read_qt_int32(data)
    return indexes, main_account


def _compute_data_name_key(dataname: str) -> str:
    """计算数据名称映射键。"""
    file_key = hashlib.md5(dataname.encode('utf8')).digest()[:8]
    return ''.join(f'{b:X}'[::-1] for b in file_key)


def _compose_account_name(dataname: str, index: int) -> str:
    """组合生成账户名称。"""
    return f'{dataname}#{index + 1}' if index > 0 else dataname


def _read_mtp_authorization_user_id(data: BytesIO) -> int:
    """读取账户授权用户标识。"""
    legacy_user_id = read_qt_int32(data)
    legacy_main_dc_id = read_qt_int32(data)

    if legacy_user_id == -1 and legacy_main_dc_id == -1:
        return read_qt_uint64(data)
    return legacy_user_id


def decrypt_accounts_internal(tdata_path: str, passcode: str = None) -> List[Dict[str, Any]]:
    """解密内部账户列表。"""
    base_path = str(tdata_path)
    key_data_path = os.path.join(base_path, f'key_{DEFAULT_DATANAME}')
    key_data_tdf = read_tdf_file(key_data_path)

    passcode_bytes = (passcode or '').encode()
    local_key, account_indexes_data = decrypt_key_data_tdf(passcode_bytes, key_data_tdf)
    account_indexes, _ = read_key_data_accounts(BytesIO(account_indexes_data))

    accounts = []
    for index in account_indexes:
        dataname_key = _compute_data_name_key(_compose_account_name(DEFAULT_DATANAME, index))
        account_file_path = os.path.join(base_path, dataname_key)
        version, encrypted_data = read_encrypted_file(account_file_path, local_key)

        blocks = read_settings_blocks(version, BytesIO(encrypted_data))
        mtp_authorization = blocks[SettingsBlocks.dbiMtpAuthorization]
        user_id = _read_mtp_authorization_user_id(BytesIO(mtp_authorization))

        accounts.append({
            'index': index,
            'user_id': user_id,
        })
    return accounts


class AccountDataCryptoService:
    """账户数据解密服务。"""

    @staticmethod
    def decrypt_accounts(tdata_path: Path, passcode: Optional[str] = None) -> List[Dict[str, Any]]:
        """解析并解密账户列表。"""
        try:
            return decrypt_accounts_internal(str(tdata_path), passcode)
        except Exception as e:
            from src.core.logger import Logger
            Logger().exception("解密账户失败", e)
            return []

    @staticmethod
    def decrypt_account_id(tdata_path: Path, passcode: Optional[str] = None) -> Optional[str]:
        """解密账户用户标识。"""
        accounts = AccountDataCryptoService.decrypt_accounts(tdata_path, passcode)
        if accounts and "user_id" in accounts[0]:
            return str(accounts[0]["user_id"])
        return None
