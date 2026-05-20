"""
AES-GCM 加密模块。

用于保护 Telegram 账户的 key_datas 文件，支持自动密钥长度规范化、
加密状态检测、文件和字节数据的加解密操作。
"""
import os
from pathlib import Path

import cryptography.exceptions
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from src.core.exceptions import TASCipherException
from src.core.interfaces import ICipherService


class AESCipher(ICipherService):
    """AES-GCM 加密器。"""

    GCM_MARKER = b'\x47\x43\x4d'
    NONCE_SIZE = 12
    TAG_SIZE = 16

    def __init__(self, key):
        """初始化加密器。"""
        self.key = self._normalize_key(key)

    @staticmethod
    def _normalize_key(key) -> bytes:
        """把密钥截断或补零到 AES 支持的 16/24/32 字节长度。"""
        key_bytes = key if isinstance(key, bytes) else key.encode('utf-8')
        if len(key_bytes) < 16:
            return key_bytes.ljust(16, b'\0')
        elif len(key_bytes) < 24:
            return key_bytes[:16]
        elif len(key_bytes) < 32:
            return key_bytes[:24]
        return key_bytes[:32]

    def encrypt(self, path: str | Path, save: bool = True) -> bool:
        """加密文件。如果文件已经是加密状态则跳过。"""
        if not isinstance(path, Path):
            path = Path(path)

        if not path.exists():
            raise TASCipherException(f"文件不存在: {path}")

        if self.is_encrypted(path):
            return True

        try:
            encrypted_data = self._encrypt_bytes(path.read_bytes())
            if save:
                path.write_bytes(encrypted_data)
            return True
        except (OSError, ValueError) as e:
            raise TASCipherException(f"加密失败: {e}") from e

    def decrypt(self, path: str | Path, save: bool = True) -> bool:
        """解密文件。如果文件不是加密数据则原样返回。"""
        if not isinstance(path, Path):
            path = Path(path)

        if not path.exists():
            raise TASCipherException(f"文件不存在: {path}")

        if not self.is_encrypted(path):
            return True

        try:
            encrypted_data = path.read_bytes()
            decrypted_data = self._decrypt_bytes(encrypted_data)
            if save:
                path.write_bytes(decrypted_data)
            return True
        except TASCipherException:
            raise
        except (OSError, ValueError) as e:
            raise TASCipherException(f"解密失败: {e}") from e

    def encrypt_bytes(self, data: bytes) -> bytes:
        """加密字节数据。如果数据已加密则原样返回。"""
        if self.is_encrypted(data):
            return data
        return self._encrypt_bytes(data)

    def decrypt_bytes(self, data: bytes) -> bytes:
        """解密字节数据。如果数据不是加密格式则原样返回。"""
        if not self.is_encrypted(data):
            return data
        return self._decrypt_bytes(data)

    def _encrypt_bytes(self, data: bytes) -> bytes:
        """内部加密实现。输出格式：GCM_MARKER + nonce + tag + ciphertext"""
        nonce = os.urandom(self.NONCE_SIZE)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()

        # noinspection PyUnresolvedReferences
        return self.GCM_MARKER + nonce + encryptor.tag + ciphertext

    def _decrypt_bytes(self, data: bytes) -> bytes:
        """内部解密实现。密钥错误或数据损坏时抛出 TASCipherException。"""
        data = data[len(self.GCM_MARKER):]

        if len(data) < self.NONCE_SIZE + self.TAG_SIZE:
            raise TASCipherException("加密数据格式错误")

        nonce = data[:self.NONCE_SIZE]
        tag = data[self.NONCE_SIZE:self.NONCE_SIZE + self.TAG_SIZE]
        ciphertext = data[self.NONCE_SIZE + self.TAG_SIZE:]

        cipher = Cipher(algorithms.AES(self.key), modes.GCM(nonce, tag))
        decryptor = cipher.decryptor()

        try:
            return decryptor.update(ciphertext) + decryptor.finalize()
        except cryptography.exceptions.InvalidTag as e:
            raise TASCipherException(f"解密失败: 密钥错误或数据被篡改") from e
        except ValueError as e:
            raise TASCipherException(f"解密失败: 密钥错误或数据损坏") from e

    @staticmethod
    def is_encrypted(path_or_bytes: str | Path | bytes) -> bool:
        """检查数据是否已加密。通过文件头部的 GCM_MARKER 判断。"""
        try:
            if isinstance(path_or_bytes, (str, Path)):
                path = Path(path_or_bytes)
                if not path.exists() or not path.is_file():
                    return False
                header = path.read_bytes()[:len(AESCipher.GCM_MARKER)]
            else:
                header = path_or_bytes[:len(AESCipher.GCM_MARKER)]
            return header == AESCipher.GCM_MARKER
        except (OSError, TypeError):
            return False
