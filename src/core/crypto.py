"""文件加解密工具."""

import os
from pathlib import Path

import cryptography.exceptions
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from src.core.constants import GCM_MARKER, NONCE_SIZE, TAG_SIZE
from src.core.exceptions import TASCipherException


class AESCipher:
    """AES-256-GCM 加解密器."""

    GCM_MARKER = GCM_MARKER
    NONCE_SIZE = NONCE_SIZE
    TAG_SIZE = TAG_SIZE

    def __init__(self, key: str) -> None:
        """初始化解密密钥."""
        self.key = self._normalize_key(key)

    @staticmethod
    def _normalize_key(key: str) -> bytes:
        """规整密钥字节."""
        key_bytes = key if isinstance(key, bytes) else key.encode("utf-8")
        if len(key_bytes) < 16:
            return key_bytes.ljust(16, b"\0")
        elif len(key_bytes) < 24:
            return key_bytes[:16]
        elif len(key_bytes) < 32:
            return key_bytes[:24]
        return key_bytes[:32]

    def encrypt(self, path: str | Path, save: bool = True) -> bool:
        """加密指定路径的文件."""
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
        """解密指定路径的文件."""
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
        """加密二进制数据."""
        if self.is_encrypted(data):
            return data
        return self._encrypt_bytes(data)

    def decrypt_bytes(self, data: bytes) -> bytes:
        """解密二进制数据."""
        if not self.is_encrypted(data):
            return data
        return self._decrypt_bytes(data)

    def _encrypt_bytes(self, data: bytes) -> bytes:
        """加密二进制字节."""
        nonce = os.urandom(self.NONCE_SIZE)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()

        # noinspection PyUnresolvedReferences
        return self.GCM_MARKER + nonce + encryptor.tag + ciphertext

    def _decrypt_bytes(self, data: bytes) -> bytes:
        """解密二进制字节."""
        data = data[len(self.GCM_MARKER) :]

        if len(data) < self.NONCE_SIZE + self.TAG_SIZE:
            raise TASCipherException("加密数据格式错误")

        nonce = data[: self.NONCE_SIZE]
        tag = data[self.NONCE_SIZE : self.NONCE_SIZE + self.TAG_SIZE]
        ciphertext = data[self.NONCE_SIZE + self.TAG_SIZE :]

        cipher = Cipher(algorithms.AES(self.key), modes.GCM(nonce, tag))
        decryptor = cipher.decryptor()

        try:
            return decryptor.update(ciphertext) + decryptor.finalize()
        except cryptography.exceptions.InvalidTag as e:
            raise TASCipherException("解密失败: 密钥错误或数据被篡改") from e
        except ValueError as e:
            raise TASCipherException("解密失败: 密钥错误或数据损坏") from e

    @staticmethod
    def is_encrypted(path_or_bytes: str | Path | bytes) -> bool:
        """检查数据是否已被加密."""
        try:
            if isinstance(path_or_bytes, (str, Path)):
                path = Path(path_or_bytes)
                if not path.exists() or not path.is_file():
                    return False
                header = path.read_bytes()[: len(AESCipher.GCM_MARKER)]
            else:
                header = path_or_bytes[: len(AESCipher.GCM_MARKER)]
            return header == AESCipher.GCM_MARKER
        except (OSError, TypeError):
            return False
