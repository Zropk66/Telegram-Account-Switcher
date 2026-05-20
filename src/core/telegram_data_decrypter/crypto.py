"""
Telegram 本地数据加解密核心。

实现了 Telegram 桌面端用于保护本地缓存的加密方案，
包括密钥派生（PBKDF2）、AES-256-IGE 解密及完整性校验。
"""
import hashlib
import tgcrypto

# 密钥派生迭代计数
LOCAL_ITER_NO_PWD = 4
LOCAL_ITER_WITH_PWD = 400
STRONG_ITER_COUNT = 100000


class CryptoException(Exception):
    """加解密过程中的错误（密码错误、数据损坏等）。"""
    pass


def create_local_key(passcode: bytes, salt: bytes) -> bytes:
    """
    使用 PBKDF2-HMAC-SHA512 派生本地加密密钥。
    无密码时迭代 1 次，有密码时使用强迭代。
    """
    iterations = STRONG_ITER_COUNT if passcode else 1
    # 先做一层 SHA512 预处理
    password = hashlib.sha512(salt + passcode + salt).digest()
    return hashlib.pbkdf2_hmac('sha512', password, salt, iterations, 256)


def create_legacy_local_key(passcode: bytes, salt: bytes) -> bytes:
    """使用旧版算法（PBKDF2-HMAC-SHA1）派生密钥。"""
    iterations = LOCAL_ITER_WITH_PWD if passcode else LOCAL_ITER_NO_PWD
    return hashlib.pbkdf2_hmac('sha1', passcode, salt, iterations, 256)


def decrypt_local(encrypted_msg: bytes, local_key: bytes) -> bytes:
    """
    解密本地存储消息并验证完整性。

    数据结构: [16 bytes msg_key][encrypted_data]
    验证方式: SHA1(decrypted)[:16] == msg_key
    """
    msg_key, encrypted_data = encrypted_msg[:16], encrypted_msg[16:]

    decrypted = aes_decrypt_local(encrypted_data, msg_key, local_key)

    # 完整性校验
    if hashlib.sha1(decrypted).digest()[:16] != msg_key:
        raise CryptoException('密钥错误或数据已损坏')

    # Telegram 数据前 4 字节为长度前缀
    length = int.from_bytes(decrypted[:4], 'little')
    if length > len(decrypted) - 4:
        raise CryptoException(f'数据长度校验失败: {length}')

    return decrypted[4:4 + length]


def aes_decrypt_local(encrypted_data: bytes, msg_key: bytes, local_key: bytes) -> bytes:
    """使用 AES-256-IGE 模式进行解密。"""
    aes_key, aes_iv = prepare_aes_old_mtp(local_key, msg_key)
    return tgcrypto.ige256_decrypt(encrypted_data, aes_key, aes_iv)


def prepare_aes_old_mtp(local_key: bytes, msg_key: bytes, send: bool = False) -> tuple:
    """
    基于 Telegram 旧版协议从 local_key 和 msg_key 派生 AES-256 密钥与 IV。
    """
    x = 0 if send else 8

    def key_part(pos, size): return local_key[pos:pos + size]

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
