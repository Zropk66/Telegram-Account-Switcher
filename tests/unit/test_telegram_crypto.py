"""
Telegram 本地数据解密模块单元测试。

验证 Telegram 本地数据解密算法的兼容性，包括密钥派生、完整性校验和 AES 参数生成。
"""
import hashlib
import pytest
from unittest.mock import patch

from src.core.telegram_data_decrypter.crypto import (
    create_local_key,
    create_legacy_local_key,
    decrypt_local,
    prepare_aes_old_mtp,
    CryptoException,
    STRONG_ITER_COUNT,
    LOCAL_ITER_WITH_PWD,
    LOCAL_ITER_NO_PWD
)


class TestTelegramCrypto:
    """覆盖 Telegram 数据解密链路中最容易因协议差异失效的部分。"""

    def test_create_local_key_with_passcode(self):
        """验证有密码账户使用新版 PBKDF2-HMAC-SHA512 参数派生本地密钥。"""
        passcode = b"test_password_123"
        salt = b"test_salt_abc"

        key = create_local_key(passcode, salt)

        assert len(key) == 256, f"密钥应为 256 字节，实际为 {len(key)} 字节"

        with patch('hashlib.pbkdf2_hmac') as mock_pbkdf2:
            mock_pbkdf2.return_value = b"x" * 256
            create_local_key(passcode, salt)

            mock_pbkdf2.assert_called_once()
            call_args = mock_pbkdf2.call_args
            assert call_args[0][0] == 'sha512', f"应使用 SHA-512，实际为 {call_args[0][0]}"
            assert call_args[0][3] == STRONG_ITER_COUNT, f"迭代次数应为 {STRONG_ITER_COUNT}，实际为 {call_args[0][3]}"
            assert call_args[0][4] == 256, f"密钥长度参数应为 256，实际为 {call_args[0][4]}"

    def test_create_local_key_no_passcode(self):
        """验证无密码账户使用 Telegram 兼容的低迭代派生路径。"""
        passcode = b""
        salt = b"test_salt_abc"

        key = create_local_key(passcode, salt)
        assert len(key) == 256

        with patch('hashlib.pbkdf2_hmac') as mock_pbkdf2:
            mock_pbkdf2.return_value = b"x" * 256
            create_local_key(passcode, salt)

            mock_pbkdf2.assert_called_once()
            assert mock_pbkdf2.call_args[0][3] == 1, f"无密码时迭代次数应为 1，实际为 {mock_pbkdf2.call_args[0][3]}"

    def test_create_legacy_local_key(self):
        """验证旧版 Telegram 客户端的 SHA-1 密钥派生逻辑仍保持兼容。"""
        passcode = b"legacy_password"
        salt = b"legacy_salt"

        key = create_legacy_local_key(passcode, salt)
        assert len(key) == 256

        with patch('hashlib.pbkdf2_hmac') as mock_pbkdf2:
            mock_pbkdf2.return_value = b"x" * 256
            create_legacy_local_key(passcode, salt)

            mock_pbkdf2.assert_called_once()
            call_args = mock_pbkdf2.call_args
            assert call_args[0][0] == 'sha1', f"旧版应使用 SHA-1，实际为 {call_args[0][0]}"
            assert call_args[0][3] == LOCAL_ITER_WITH_PWD, f"有密码时迭代次数应为 {LOCAL_ITER_WITH_PWD}，实际为 {call_args[0][3]}"
            assert call_args[0][4] == 256, f"密钥长度参数应为 256，实际为 {call_args[0][4]}"

        with patch('hashlib.pbkdf2_hmac') as mock_pbkdf2:
            mock_pbkdf2.return_value = b"x" * 256
            create_legacy_local_key(b"", salt)

            mock_pbkdf2.assert_called_once()
            assert mock_pbkdf2.call_args[0][3] == LOCAL_ITER_NO_PWD, f"无密码时迭代次数应为 {LOCAL_ITER_NO_PWD}，实际为 {mock_pbkdf2.call_args[0][3]}"

    def test_decrypt_local_integrity_check(self):
        """验证完整性校验失败时拒绝返回错误明文。"""
        msg_key = b"0123456789abcdef"
        encrypted_data = b"some_encrypted_data_here!!"
        encrypted_msg = msg_key + encrypted_data

        local_key = b"test_local_key_32_bytes_long!!!"

        with patch('src.core.telegram_data_decrypter.crypto.tgcrypto') as mock_tgcrypto:
            bad_decrypted = b"bad_decrypted_data_that_will_not_match_msg_key!!!"
            mock_tgcrypto.ige256_decrypt.return_value = bad_decrypted

            with pytest.raises(CryptoException) as exc_info:
                decrypt_local(encrypted_msg, local_key)

            assert str(exc_info.value)
            mock_tgcrypto.ige256_decrypt.assert_called_once()

        with patch('src.core.telegram_data_decrypter.crypto.tgcrypto') as mock_tgcrypto:
            data_length = 10
            length_bytes = data_length.to_bytes(4, 'little')
            actual_data = b"1234567890"
            decrypted = length_bytes + actual_data + b"padding"
            correct_msg_key = hashlib.sha1(decrypted).digest()[:16]

            mock_tgcrypto.ige256_decrypt.return_value = decrypted
            result = decrypt_local(correct_msg_key + encrypted_data, local_key)

            assert result == actual_data

    def test_prepare_aes_old_mtp(self):
        """验证旧版 MTP 协议的 AES 密钥和 IV 派生算法保持准确。"""
        local_key = bytes(range(128))
        msg_key = b"0123456789abcdef"

        key, iv = prepare_aes_old_mtp(local_key, msg_key, send=False)

        assert len(key) == 32, f"AES 密钥应为 32 字节，实际为 {len(key)}"
        assert len(iv) == 32, f"AES IV 应为 32 字节，实际为 {len(iv)}"

        key_send, iv_send = prepare_aes_old_mtp(local_key, msg_key, send=True)

        assert key != key_send, "发送模式和接收模式应产生不同的密钥"
        assert iv != iv_send, "发送模式和接收模式应产生不同的 IV"

        x = 8

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

        expected_key = sha1A[:8] + sha1B[8:20] + sha1C[4:16]
        expected_iv = sha1A[8:20] + sha1B[:8] + sha1C[16:20] + sha1D[:8]

        assert key == expected_key, "密钥派生算法不正确"
        assert iv == expected_iv, "IV 派生算法不正确"
