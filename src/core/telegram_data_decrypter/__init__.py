"""Telegram 本地数据解密模块。

本模块提供解密 Telegram 桌面端本地缓存数据的核心功能，
包括：

- 密钥派生与加密解密（crypto 模块）
- TDF 文件格式解析（tdf 模块）
- Qt 二进制数据读取（qt 模块）
- 账户数据解密与提取（main 模块）

典型用法::

    from src.core.telegram_data_decrypter import decrypt_accounts

    accounts = decrypt_accounts('/path/to/tdata', passcode='your_passcode')
    for account in accounts:
        print(f"用户 ID: {account['user_id']}")
"""

from src.core.telegram_data_decrypter.main import decrypt_accounts

__all__ = ['decrypt_accounts']
