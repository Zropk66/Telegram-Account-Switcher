from pathlib import Path
from typing import Optional, List, Dict, Any


class AccountDataCryptoService:
    """封装 Telegram tdata 的解密能力，供外部模块调用。"""

    @staticmethod
    def decrypt_accounts(tdata_path: Path, passcode: Optional[str] = None) -> List[Dict[str, Any]]:
        """解密指定 tdata 目录，返回所有账户信息。"""
        try:
            import src.core.telegram_data_decrypter.main as tdd
            return tdd.decrypt_accounts(str(tdata_path), passcode)
        except Exception:
            return []

    @staticmethod
    def decrypt_account_id(tdata_path: Path, passcode: Optional[str] = None) -> Optional[str]:
        """只取 tdata 下第一个账户的 user_id。"""
        accounts = AccountDataCryptoService.decrypt_accounts(tdata_path, passcode)
        if accounts and accounts[0].get('user_id'):
            return str(accounts[0].get('user_id'))
        return None
