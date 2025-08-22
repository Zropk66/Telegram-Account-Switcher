# -*- coding: utf-8 -*-
# @File ： aes_crypto.py
# @Time : 2025/7/23 20:08
# @Author : Zropk
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

from src.modules.exceptions import TASCipherException


class AESCipher:
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
            raise TASCipherException(f"密钥类型 {type(s)} 不受支持. 当前仅支持[ {str}, {bytes}, {bytearray} ].")

    def _handle_cipher(self, path: str | Path, method: str, save: bool):
        """加解密"""
        try:
            if not isinstance(path, Path):
                path = Path(path)
            if not path.is_file():
                raise TASCipherException(f"路径 -> {path} 不是有效文件.")
            data = self._cipher_process(path.read_bytes(), method)
            if save:
                path.write_bytes(data)
                return True
        except TASCipherException as e:
            raise e

    def _cipher_process(self, data: bytes, method: str) -> bytes:
        """加解密主方法"""
        if not isinstance(data, bytes):
            raise TASCipherException(f"输入的数据类型必须为 {bytes}")

        cipher = Cipher(algorithms.AES(self.key), modes.ECB(), backend=default_backend())

        cipher_operator = {
            self.METHOD_ENCRYPT: cipher.encryptor(),
            self.METHOD_DECRYPT: cipher.decryptor()
        }.get(method)
        try:
            if method == self.METHOD_ENCRYPT:
                return cipher_operator.update(self.__data_process(data, method)) + cipher_operator.finalize()
            elif method == self.METHOD_DECRYPT:
                return self.__data_process(
                    cipher_operator.update(data) + cipher_operator.finalize(),
                    self.METHOD_DECRYPT
                )
            else:
                raise TASCipherException(f"无效模式")
        except ValueError as e:
            raise TASCipherException('解密失败.') from e

    def __data_process(self, data: bytes, method: str) -> bytes:
        """填充和去除数据"""
        if not isinstance(data, bytes):
            raise TASCipherException(f"输入数据必须为 {bytes}")
        try:
            pad = {
                self.METHOD_ENCRYPT: padding.PKCS7(128).padder(),
                self.METHOD_DECRYPT: padding.PKCS7(128).unpadder()
            }.get(method)
            if not pad:
                raise TASCipherException(f"无效模式")
            return pad.update(data) + pad.finalize()
        except ValueError as e:
            raise TASCipherException(f"数据填充/删除失败: {str(e)}") from e

    def encrypt(self, path: str | Path, save: bool = True):
        """加密"""
        return self._handle_cipher(path, self.METHOD_ENCRYPT, save)

    def decrypt(self, path: str | Path, save: bool = True):
        """解密"""
        return self._handle_cipher(path, self.METHOD_DECRYPT, save)
