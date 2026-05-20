"""
AESCipher 加密模块单元测试。

验证 AES-GCM 加密实现的边界行为、往返一致性和完整性保护能力。
"""
import pytest
from pathlib import Path

from src.core.crypto import AESCipher
from src.core.exceptions import TASCipherException


class TestAESCipher:
    """覆盖账户数据加密链路中的关键安全约束。"""

    def test_key_normalization_all_boundaries(self):
        """验证任意长度密钥都会被规整到 AES 支持的合法长度。"""
        key_15 = b'a' * 15
        key_16 = b'a' * 16
        key_17 = b'a' * 17
        key_24 = b'a' * 24
        key_25 = b'a' * 25
        key_32 = b'a' * 32
        key_33 = b'a' * 33
        key_40 = b'a' * 40

        cipher_15 = AESCipher(key_15)
        cipher_16 = AESCipher(key_16)
        cipher_17 = AESCipher(key_17)
        cipher_24 = AESCipher(key_24)
        cipher_25 = AESCipher(key_25)
        cipher_32 = AESCipher(key_32)
        cipher_33 = AESCipher(key_33)
        cipher_40 = AESCipher(key_40)

        assert len(cipher_15.key) == 16
        assert len(cipher_16.key) == 16
        assert len(cipher_17.key) == 16
        assert len(cipher_24.key) == 24
        assert len(cipher_25.key) == 24
        assert len(cipher_32.key) == 32
        assert len(cipher_33.key) == 32
        assert len(cipher_40.key) == 32

    def test_encrypt_decrypt_roundtrip(self):
        """验证加密数据可被同一密钥完整解回原文。"""
        test_data = b'Hello, this is a test message for encryption!'
        cipher = AESCipher(b'test_key')

        encrypted = cipher.encrypt_bytes(test_data)
        assert encrypted != test_data

        decrypted = cipher.decrypt_bytes(encrypted)
        assert decrypted == test_data

    def test_encryption_idempotency(self, cleanup_temp_files):
        """验证已加密文件重复加密不会破坏既有密文。"""
        cipher = AESCipher(b'test_key')
        test_path = Path('test_encrypted_file.tmp')
        cleanup_temp_files.append(test_path)

        test_data = b'Original data'
        test_path.write_bytes(test_data)

        cipher.encrypt(test_path)
        encrypted1 = test_path.read_bytes()
        assert AESCipher.is_encrypted(encrypted1)

        cipher.encrypt(test_path)
        encrypted2 = test_path.read_bytes()
        assert encrypted2 == encrypted1

    def test_decrypt_wrong_key_raises(self):
        """验证错误密钥不能静默产出伪造明文。"""
        test_data = b'Secret data'
        cipher1 = AESCipher(b'correct_key')
        cipher2 = AESCipher(b'wrong_key')

        encrypted = cipher1.encrypt_bytes(test_data)

        with pytest.raises(TASCipherException):
            cipher2.decrypt_bytes(encrypted)

    def test_tampered_ciphertext_detected(self):
        """验证密文任意位置被篡改时，GCM 认证会拒绝解密。"""
        cipher = AESCipher(b'test_key')
        test_data = b'Important data'

        encrypted = cipher.encrypt_bytes(test_data)

        tampered = encrypted[:-1] + b'X'
        with pytest.raises(TASCipherException):
            cipher.decrypt_bytes(tampered)

        mid_tampered = encrypted[:20] + b'X' + encrypted[21:]
        with pytest.raises(TASCipherException):
            cipher.decrypt_bytes(mid_tampered)

    def test_is_encrypted_detection(self, cleanup_temp_files):
        """验证文件和字节数据都能通过加密标记正确识别状态。"""
        cipher = AESCipher(b'test_key')
        test_path = Path('test_detection.tmp')
        cleanup_temp_files.append(test_path)

        plain_data = b'Plain text'
        test_path.write_bytes(plain_data)
        assert AESCipher.is_encrypted(test_path) is False
        assert AESCipher.is_encrypted(plain_data) is False

        cipher.encrypt(test_path)
        encrypted_data = test_path.read_bytes()
        assert AESCipher.is_encrypted(test_path) is True
        assert AESCipher.is_encrypted(encrypted_data) is True
