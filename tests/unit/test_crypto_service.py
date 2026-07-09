"""
AccountDataCryptoService 与 Telegram 底层解密功能单元测试。
"""

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.crypto_service import (
    LOCAL_ITER_NO_PWD,
    LOCAL_ITER_WITH_PWD,
    STRONG_ITER_COUNT,
    AccountDataCryptoService,
    CryptoException,
    RawTdfFile,
    create_legacy_local_key,
    create_local_key,
    decrypt_key_data_tdf,
    decrypt_local,
    prepare_aes_old_mtp,
)


def test_decrypt_accounts_exception_safety():
    """验证 decrypt_accounts 遇到任何异常时都能安全捕获并返回空列表，避免崩溃。"""
    with patch("src.core.crypto_service.decrypt_accounts_internal", side_effect=CryptoException("Test error")):
        result = AccountDataCryptoService.decrypt_accounts(Path("/fake/path"), "passcode")
        assert result == []

    with patch("src.core.crypto_service.decrypt_accounts_internal", side_effect=ValueError("Value error")):
        result = AccountDataCryptoService.decrypt_accounts(Path("/fake/path"), "passcode")
        assert result == []

    with patch("src.core.crypto_service.decrypt_accounts_internal", side_effect=RuntimeError("Runtime error")):
        result = AccountDataCryptoService.decrypt_accounts(Path("/fake/path"), "passcode")
        assert result == []

    with patch("src.core.crypto_service.decrypt_accounts_internal", side_effect=Exception("General exception")):
        result = AccountDataCryptoService.decrypt_accounts(Path("/fake/path"), "passcode")
        assert result == []


class TestTelegramCrypto:
    """覆盖 Telegram 数据解密链路中关键函数的单元测试。"""

    def test_create_local_key_with_passcode(self):
        """验证有密码账户使用新版 PBKDF2-HMAC-SHA512 参数派生本地密钥。"""
        passcode = b"test_password_123"
        salt = b"test_salt_abc"

        key = create_local_key(passcode, salt)

        assert len(key) == 256, f"密钥应为 256 字节，实际为 {len(key)} 字节"

        with patch("hashlib.pbkdf2_hmac") as mock_pbkdf2:
            mock_pbkdf2.return_value = b"x" * 256
            create_local_key(passcode, salt)

            mock_pbkdf2.assert_called_once()
            call_args = mock_pbkdf2.call_args
            assert call_args[0][0] == "sha512", f"应使用 SHA-512，实际为 {call_args[0][0]}"
            assert call_args[0][3] == STRONG_ITER_COUNT, f"迭代次数应为 {STRONG_ITER_COUNT}，实际为 {call_args[0][3]}"
            assert call_args[0][4] == 256, f"密钥长度参数应为 256，实际为 {call_args[0][4]}"

    def test_create_local_key_no_passcode(self):
        """验证无密码账户使用 Telegram 兼容的低迭代派生路径。"""
        passcode = b""
        salt = b"test_salt_abc"

        key = create_local_key(passcode, salt)
        assert len(key) == 256

        with patch("hashlib.pbkdf2_hmac") as mock_pbkdf2:
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

        with patch("hashlib.pbkdf2_hmac") as mock_pbkdf2:
            mock_pbkdf2.return_value = b"x" * 256
            create_legacy_local_key(passcode, salt)

            mock_pbkdf2.assert_called_once()
            call_args = mock_pbkdf2.call_args
            assert call_args[0][0] == "sha1", f"旧版应使用 SHA-1，实际为 {call_args[0][0]}"
            assert call_args[0][3] == LOCAL_ITER_WITH_PWD, (
                f"有密码时迭代次数应为 {LOCAL_ITER_WITH_PWD}，实际为 {call_args[0][3]}"
            )
            assert call_args[0][4] == 256, f"密钥长度参数应为 256，实际为 {call_args[0][4]}"

        with patch("hashlib.pbkdf2_hmac") as mock_pbkdf2:
            mock_pbkdf2.return_value = b"x" * 256
            create_legacy_local_key(b"", salt)

            mock_pbkdf2.assert_called_once()
            assert mock_pbkdf2.call_args[0][3] == LOCAL_ITER_NO_PWD, (
                f"无密码时迭代次数应为 {LOCAL_ITER_NO_PWD}，实际为 {mock_pbkdf2.call_args[0][3]}"
            )

    def test_decrypt_local_integrity_check(self):
        """验证完整性校验失败时拒绝返回错误明文。"""
        msg_key = b"0123456789abcdef"
        encrypted_data = b"some_encrypted_data_here!!"
        encrypted_msg = msg_key + encrypted_data

        local_key = b"test_local_key_32_bytes_long!!!"

        with patch("src.core.crypto_service.tgcrypto") as mock_tgcrypto:
            bad_decrypted = b"bad_decrypted_data_that_will_not_match_msg_key!!!"
            mock_tgcrypto.ige256_decrypt.return_value = bad_decrypted

            with pytest.raises(CryptoException) as exc_info:
                decrypt_local(encrypted_msg, local_key)

            assert str(exc_info.value)
            mock_tgcrypto.ige256_decrypt.assert_called_once()

        with patch("src.core.crypto_service.tgcrypto") as mock_tgcrypto:
            actual_data = b"1234567890"
            data_length = len(actual_data) + 4
            length_bytes = data_length.to_bytes(4, "little")
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
            """获取密钥片段。"""
            return local_key[pos : pos + size]

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

    def test_decrypt_key_data_tdf_fallback(self):
        """验证新版 PBKDF2-HMAC-SHA512 解密失败时，能 fallback 到旧版 PBKDF2-HMAC-SHA1 解密。"""
        passcode = b"my_password"
        salt = b"salt_bytes"
        key_encrypted = b"key_enc"
        info_encrypted = b"info_enc"

        def to_qt_byte_array(data: bytes) -> bytes:
            """转换为 Qt 字节数组。"""
            return len(data).to_bytes(4, "big") + data

        encrypted_payload = to_qt_byte_array(salt) + to_qt_byte_array(key_encrypted) + to_qt_byte_array(info_encrypted)
        tdf_file = RawTdfFile(version=1, encrypted_data=encrypted_payload)

        with (
            patch("src.core.crypto_service.create_local_key") as mock_new_key,
            patch("src.core.crypto_service.create_legacy_local_key") as mock_legacy_key,
            patch("src.core.crypto_service.decrypt_local") as mock_decrypt,
        ):
            mock_new_key.return_value = b"new_pass_key"
            mock_legacy_key.return_value = b"legacy_pass_key"

            local_key = b"root_local_key"
            info_decrypted = b"info_decrypted_bytes"

            def mock_decrypt_side_effect(data, key):
                """模拟解密逻辑。"""
                if key == b"new_pass_key":
                    raise CryptoException("Decryption failed")
                elif key == b"legacy_pass_key" and data == key_encrypted:
                    return local_key
                elif key == local_key and data == info_encrypted:
                    return info_decrypted
                raise ValueError("Unexpected args")

            mock_decrypt.side_effect = mock_decrypt_side_effect

            res_local_key, res_info = decrypt_key_data_tdf(passcode, tdf_file)

            assert res_local_key == local_key
            assert res_info == info_decrypted
            mock_new_key.assert_called_once_with(passcode, salt)
            mock_legacy_key.assert_called_once_with(passcode, salt)
            assert mock_decrypt.call_count == 3

    def test_parse_raw_tdf(self):
        """验证 parse_raw_tdf 正确识别 TDF$ 魔数并切片出 version 和 encrypted_data。"""
        from src.core.crypto_service import CryptoException, parse_raw_tdf

        magic = b"TDF$"
        version_bytes = (123).to_bytes(4, "little")
        encrypted_data = b"encrypted_payload_content"
        md5_bytes = b"0123456789abcdef"  # 16字节
        raw_data = magic + version_bytes + encrypted_data + md5_bytes

        res = parse_raw_tdf(raw_data)
        assert res.version == 123
        assert res.encrypted_data == encrypted_data

        wrong_magic_data = b"TDF#" + version_bytes + encrypted_data + md5_bytes
        with pytest.raises(CryptoException, match="魔数不匹配"):
            parse_raw_tdf(wrong_magic_data)

        short_data = b"TDF$"
        with pytest.raises(CryptoException, match="数据过短"):
            parse_raw_tdf(short_data)
