# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional, List, Dict, Any


class AccountDataCryptoService:
    """Telegram 数据加密处理"""

    @staticmethod
    def decrypt_accounts(tdata_path: Path, passcode: Optional[str] = None) -> List[Dict[str, Any]]:
        """解密 Telegram tdata 目录，返回账户信息列表"""
        try:
            import src.modules.telegram_data_decrypter.main as tdd
            return tdd.decrypt_accounts(str(tdata_path), passcode)
        except Exception:
            return []

    @staticmethod
    def decrypt_account_id(tdata_path: Path, passcode: Optional[str] = None) -> Optional[str]:
        """获取 tdata 目录下的第一个账户 user_id"""
        accounts = AccountDataCryptoService.decrypt_accounts(tdata_path, passcode)
        if accounts and accounts[0].get('user_id'):
            return str(accounts[0].get('user_id'))
        return None
