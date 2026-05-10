# -*- coding: utf-8 -*-
# @File ： crypto.py
# @Time : 2025/7/23 20:08
# @Author : Zropk
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from src.modules.exceptions import TASCipherException


class AESCipher:
    """AES-GCM 加密器"""

    GCM_MARKER = b'\x47\x43\x4d'
    NONCE_SIZE = 12
    TAG_SIZE = 16

    def __init__(self, key):
        self.key = self._normalize_key(key)

    @staticmethod
    def _normalize_key(key) -> bytes:
        """将密钥标准化为16/24/32字节"""
        key_bytes = key if isinstance(key, bytes) else key.encode('utf-8')
        if len(key_bytes) < 16:
            return key_bytes.ljust(16, b'\0')
        elif len(key_bytes) < 24:
            return key_bytes[:16]
        elif len(key_bytes) < 32:
            return key_bytes[:24]
        return key_bytes[:32]

    def encrypt(self, path: str | Path, save: bool = True) -> bool:
        """加密文件"""
        if not isinstance(path, Path):
            path = Path(path)

        if self.is_encrypted(path):
            return True

        encrypted_data = self._encrypt_bytes(path.read_bytes())
        if save:
            path.write_bytes(encrypted_data)
        return True

    def decrypt(self, path: str | Path, save: bool = True) -> bool:
        """解密文件"""
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
        """加密字节数据"""
        if self.is_encrypted(data):
            return data
        return self._encrypt_bytes(data)

    def decrypt_bytes(self, data: bytes) -> bytes:
        """解密字节数据"""
        if not self.is_encrypted(data):
            return data
        return self._decrypt_bytes(data)

    def _encrypt_bytes(self, data: bytes) -> bytes:
        """内部加密方法，返回 GCM_MARKER + nonce + tag + ciphertext"""
        nonce = os.urandom(self.NONCE_SIZE)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()

        return self.GCM_MARKER + nonce + encryptor.tag + ciphertext

    def _decrypt_bytes(self, data: bytes) -> bytes:
        """内部解密方法"""
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
        """检查是否为加密数据"""
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
