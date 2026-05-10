# -*- coding: utf-8 -*-
# @File ： crypto.py
# @Time : 2025/7/23 20:08
# @Author : Zropk
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from src.modules.exceptions import TASCipherException


class AESCipher:
    # 标记
    ENCRYPTION_MARKER = b'\xc7\xdfj\x1d\xd6\x88Y\xc8'

    def __init__(self, key):
        self.METHOD_ENCRYPT = 'encrypt'
        self.METHOD_DECRYPT = 'decrypt'
        self.key = self.get_byte(key).ljust(16, b'\0')[:16]

    @staticmethod
    def get_byte(s):
        """获取字符串的字节数组"""
        if isinstance(s, str):
            return s.encode('utf-8')
        elif isinstance(s, bytes) or isinstance(s, bytearray):
            return bytes(s)
        else:
            raise TASCipherException(
                f'密钥类型 {type(s)} 不受支持. 当前仅支持[ {str}, {bytes}, {bytearray} ].'
            )

    def _cipher_process(self, data: bytes, method: str) -> bytes:
        """执行加解密"""
        if not isinstance(data, bytes):
            raise TASCipherException(f"输入的数据类型必须为 {bytes}")

        cipher = Cipher(algorithms.AES(self.key), modes.ECB(), backend=default_backend())

        cipher_operator = {
            self.METHOD_ENCRYPT: cipher.encryptor(),
            self.METHOD_DECRYPT: cipher.decryptor()
        }.get(method)

        try:
            if method == self.METHOD_ENCRYPT:
                return (cipher_operator.update(self.__data_process(data, method))
                        + cipher_operator.finalize()
                        )
            elif method == self.METHOD_DECRYPT:
                return self.__data_process(
                    cipher_operator.update(data) + cipher_operator.finalize(), self.METHOD_DECRYPT
                )
            else:
                raise TASCipherException(f"无效模式: {method}")
        except ValueError as e:
            raise TASCipherException("加解密过程出错.") from e

    def __data_process(self, data: bytes, method: str) -> bytes:
        """数据转换处理"""
        if not isinstance(data, bytes):
            raise TASCipherException(f"输入数据必须为 {bytes}")
        try:
            pad = {
                self.METHOD_ENCRYPT: padding.PKCS7(128).padder(),
                self.METHOD_DECRYPT: padding.PKCS7(128).unpadder(),
            }.get(method)
            if not pad:
                raise TASCipherException(f"无效模式")
            return pad.update(data) + pad.finalize()
        except ValueError as e:
            msg = str(e)
            if "padding" in msg.lower():
                msg = "密钥错误或数据损坏"
            raise TASCipherException(f"数据处理失败: {msg}") from e

    @staticmethod
    def is_encrypted(path_or_bytes: str | Path | bytes) -> bool:
        """检查加密状态"""
        try:
            if isinstance(path_or_bytes, (str, Path)):
                path = Path(path_or_bytes)
                if not path.exists() or not path.is_file():
                    return False
                with open(path, 'rb') as f:
                    header = f.read(len(AESCipher.ENCRYPTION_MARKER))
            else:
                header = path_or_bytes[:len(AESCipher.ENCRYPTION_MARKER)]
            return header == AESCipher.ENCRYPTION_MARKER
        except Exception:
            return False

    def encrypt(self, path: str | Path, save: bool = True):
        """加密"""
        if not isinstance(path, Path):
            path = Path(path)

        if self.is_encrypted(path):
            return True

        encrypted_data = self._cipher_process(path.read_bytes(), self.METHOD_ENCRYPT)
        if save:
            path.write_bytes(self.ENCRYPTION_MARKER + encrypted_data)
        return True

    def decrypt(self, path: str | Path, save: bool = True):
        """解密"""
        if not isinstance(path, Path):
            path = Path(path)

        if not self.is_encrypted(path):
            return True

        encrypted_data = path.read_bytes()
        data_without_marker = encrypted_data[len(self.ENCRYPTION_MARKER):]
        decrypted_data = self._cipher_process(data_without_marker, self.METHOD_DECRYPT)
        if save:
            path.write_bytes(decrypted_data)
        return True

    def decrypt_bytes(self, data: bytes) -> bytes:
        """解密字节数据"""
        if not self.is_encrypted(data):
            return data
        try:
            data_without_marker = data[len(self.ENCRYPTION_MARKER):]
            return self._cipher_process(data_without_marker, self.METHOD_DECRYPT)
        except Exception as e:
            raise TASCipherException(f"字节解密失败: {e}") from e

    def encrypt_bytes(self, data: bytes) -> bytes:
        """加密字节数据"""
        if self.is_encrypted(data):
            return data
        try:
            encrypted_data = self._cipher_process(data, self.METHOD_ENCRYPT)
            return self.ENCRYPTION_MARKER + encrypted_data
        except Exception as e:
            raise TASCipherException(f"字节加密失败: {e}") from e
