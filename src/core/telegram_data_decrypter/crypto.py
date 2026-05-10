"""Telegram 本地数据加密/解密核心模块。

实现 Telegram 桌面端用于保护本地缓存数据的加密方案，
包括密钥派生（PBKDF2）、AES-256-IGE 解密以及消息完整性校验。
"""

import hashlib

import tgcrypto

# -- 迭代次数常量 --
# 无密码时的旧版迭代次数，安全性较低
LocalEncryptNoPwdIterCount = 4
# 有密码时的旧版迭代次数
LocalEncryptIterCount = 400
# 当前版本使用的强迭代次数，暴力破解成本很高
kStrongIterationsCount = 100000


class CryptoException(Exception):
    """加密/解密过程中出现的错误，如密码错误或数据损坏。"""
    pass


def create_local_key(passcode: bytes, salt: bytes) -> bytes:
    """根据 passcode 和 salt 通过 SHA-512 + PBKDF2-HMAC-SHA512 派生 256 位本地加密密钥。"""
    if passcode:
        iterations = kStrongIterationsCount
    else:
        iterations = 1

    password = hashlib.sha512(salt + passcode + salt).digest()
    return hashlib.pbkdf2_hmac('sha512', password, salt, iterations, 256)


def create_legacy_local_key(passcode: bytes, salt: bytes) -> bytes:
    """旧版密钥派生算法，直接对 passcode 做 PBKDF2-HMAC-SHA1 派生 256 位密钥。"""
    if passcode:
        iterations = LocalEncryptIterCount
    else:
        iterations = LocalEncryptNoPwdIterCount

    return hashlib.pbkdf2_hmac('sha1', passcode, salt, iterations, 256)


def decrypt_local(encrypted_msg, local_key):
    """用 local_key 解密 encrypted_msg 并通过 SHA-1 校验 msg_key 完整性，返回解密后的原始数据。"""
    msg_key, encrypted_data = encrypted_msg[:16], encrypted_msg[16:]

    decrypted = aes_decrypt_local(encrypted_data, msg_key, local_key)

    # 用 SHA-1 前 16 字节和 msg_key 比对，验证解密是否正确
    if hashlib.sha1(decrypted).digest()[:16] != msg_key:
        raise CryptoException('bad decrypt key, data not decrypted - incorrect password')

    # 明文前 4 字节是小端序的数据长度
    length = int.from_bytes(decrypted[:4], 'little')
    if length > len(decrypted):
        raise CryptoException(f'corrupted data. wrong length: {length}')

    return decrypted[4:length]


def aes_decrypt_local(encrypted_data, msg_key, local_key):
    """使用 AES-256-IGE 模式解密 encrypted_data，msg_key 和 local_key 用于派生 AES 密钥和 IV。"""
    aes_key, aes_iv = prepare_aes_old_mtp(local_key, msg_key)
    return tgcrypto.ige256_decrypt(encrypted_data, aes_key, aes_iv)


def prepare_aes_old_mtp(local_key, msg_key, send=False):
    """从 local_key 和 msg_key 通过 SHA-1 交叉拼接派生 AES-256 的 32 字节密钥和 32 字节 IV。"""
    x = 0 if send else 8

    def key_pos(pos, size):
        return local_key[pos:pos + size]

    dataA = msg_key + key_pos(x, 32)
    dataB = key_pos(x + 32, 16) + msg_key + key_pos(x + 48, 16)
    dataC = key_pos(x + 64, 32) + msg_key
    dataD = msg_key + key_pos(x + 96, 32)

    sha1A = hashlib.sha1(dataA).digest()
    sha1B = hashlib.sha1(dataB).digest()
    sha1C = hashlib.sha1(dataC).digest()
    sha1D = hashlib.sha1(dataD).digest()

    # 交叉拼接四个 SHA-1 结果的片段
    key = sha1A[:8] + sha1B[8:20] + sha1C[4:16]
    iv = sha1A[8:20] + sha1B[:8] + sha1C[16:20] + sha1D[:8]

    return key, iv
