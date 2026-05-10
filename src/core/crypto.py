import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from src.core.exceptions import TASCipherException


class AESCipher:
    """AES-GCM 加解密，用于保护账户的 key_datas 文件。"""

    GCM_MARKER = b'\x47\x43\x4d'
    NONCE_SIZE = 12
    TAG_SIZE = 16

    def __init__(self, key):
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
        """加密文件，已经是加密状态的会跳过。"""
        if not isinstance(path, Path):
            path = Path(path)

        if self.is_encrypted(path):
            return True

        encrypted_data = self._encrypt_bytes(path.read_bytes())
        if save:
            path.write_bytes(encrypted_data)
        return True

    def decrypt(self, path: str | Path, save: bool = True) -> bool:
        """解密文件，非加密数据会原样返回。"""
        if not isinstance(path, Path):
            path = Path(path)

        if not self.is_encrypted(path):
            return True

        encrypted_data = path.read_bytes()
        decrypted_data = self._decrypt_bytes(encrypted_data)
        if save:
            path.write_bytes(decrypted_data)
        return True

    def encrypt_bytes(self, data: bytes) -> bytes:
        """加密一段字节，已加密的原文样返回。"""
        if self.is_encrypted(data):
            return data
        return self._encrypt_bytes(data)

    def decrypt_bytes(self, data: bytes) -> bytes:
        """解密一段字节，非加密数据原样返回。"""
        if not self.is_encrypted(data):
            return data
        return self._decrypt_bytes(data)

    def _encrypt_bytes(self, data: bytes) -> bytes:
        """内部加密，输出格式：GCM_MARKER + nonce + tag + ciphertext。"""
        nonce = os.urandom(self.NONCE_SIZE)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()

        return self.GCM_MARKER + nonce + encryptor.tag + ciphertext

    def _decrypt_bytes(self, data: bytes) -> bytes:
        """内部解密，密钥错误或数据损坏时抛出 ``TASCipherException``。"""
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
        except Exception as e:
            raise TASCipherException(f"解密失败: 密钥错误或数据损坏") from e

    @staticmethod
    def is_encrypted(path_or_bytes: str | Path | bytes) -> bool:
        """通过文件头部的 GCM_MARKER 判断是否已加密。"""
        try:
            if isinstance(path_or_bytes, (str, Path)):
                path = Path(path_or_bytes)
                if not path.exists() or not path.is_file():
                    return False
                header = path.read_bytes()[:len(AESCipher.GCM_MARKER)]
            else:
                header = path_or_bytes[:len(AESCipher.GCM_MARKER)]
            return header == AESCipher.GCM_MARKER
        except Exception:
            return False
