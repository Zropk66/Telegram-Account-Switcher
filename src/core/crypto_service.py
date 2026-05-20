"""
Telegram 账户数据解密桥接服务。

封装底层 `telegram_data_decrypter` 模块，为高层业务逻辑提供简洁的解密接口。
"""
from pathlib import Path
from typing import Optional, List, Dict, Any


class AccountDataCryptoService:
    """负责账户数据解密任务的服务类。"""

    @staticmethod
    def decrypt_accounts(tdata_path: Path, passcode: Optional[str] = None) -> List[Dict[str, Any]]:
        """解密指定 tdata 目录并提取所有账户信息。"""
        try:
            from src.core.telegram_data_decrypter import main as tdd
            return tdd.decrypt_accounts(str(tdata_path), passcode)
        except (ImportError, RuntimeError, ValueError):
            return []

    @staticmethod
    def decrypt_account_id(tdata_path: Path, passcode: Optional[str] = None) -> Optional[str]:
        """提取首个账户的 User ID。"""
        accounts = AccountDataCryptoService.decrypt_accounts(tdata_path, passcode)
        if accounts and "user_id" in accounts[0]:
            return str(accounts[0]["user_id"])
        return None
