"""密钥管理器."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from .service import ConfigService
from .config import PathConfig


class TelegramKeyManager:
    """密钥管理器."""

    _log_handler: Optional[Callable[[str], None]] = None

    @classmethod
    def set_log_handler(cls, handler: Optional[Callable[[str], None]]) -> None:
        """设置错误日志处理器."""
        cls._log_handler = handler

    @classmethod
    def _log_error(cls, message: str) -> None:
        """记录错误日志."""
        if cls._log_handler:
            try:
                cls._log_handler(message)
            except (RuntimeError, TypeError):
                pass

    @staticmethod
    def backup_keys(tag: str, folder_path: Path, config_service: ConfigService) -> bool:
        """从账户文件夹中读取并备份登录凭证密钥."""
        try:
            identity_path = PathConfig.get_identity_path(folder_path)
            info_path = PathConfig.get_info_path(folder_path)
            key_path = PathConfig.get_key_path(folder_path)

            if not (identity_path.exists() and info_path.exists() and key_path.exists()):
                return False

            data_identity = identity_path.read_bytes()
            data_info = info_path.read_bytes()
            data_key = key_path.read_bytes()

            account_data = config_service.get_account(tag)
            account_data["info"] = base64.b64encode(data_info).decode()
            account_data["identity"] = base64.b64encode(data_identity).decode()
            account_data["key"] = base64.b64encode(data_key).decode()

            config_service.set_account(tag, account_data)
            return True
        except (OSError, ValueError, TypeError) as e:
            TelegramKeyManager._log_error(f"备份账户 '{tag}' 密钥失败: {e}")
            return False

    @staticmethod
    def login_with_keys(tag: str, tdata_path: str, config_service: ConfigService) -> bool:
        """从备份的密钥还原无密码登录状态."""
        if not config_service.has_complete_keys(tag):
            return False

        try:
            account = config_service.get_account(tag)
            if not (account.get("key") and account.get("identity") and account.get("info")):
                return False
            try:
                raw_info = base64.b64decode(account["info"])
                raw_identity = base64.b64decode(account["identity"])
                raw_key = base64.b64decode(account["key"])

                if not raw_info or not raw_identity or not raw_key:
                    TelegramKeyManager._log_error("Key登录数据解码为空")
                    return False

                tdata_dir = Path(tdata_path)
                tdata_dir.mkdir(parents=True, exist_ok=True)

                info_path = PathConfig.get_info_path(tdata_dir, True)
                identity_path = PathConfig.get_identity_path(tdata_dir, True)
                key_path = PathConfig.get_key_path(tdata_dir, True)

                info_path.write_bytes(raw_info)
                identity_path.write_bytes(raw_identity)
                key_path.write_bytes(raw_key)

                return True
            except (OSError, ValueError, TypeError) as e:
                TelegramKeyManager._log_error(f"Key登录解码或写入失败: {e}")
                return False

        except (OSError, RuntimeError):
            TelegramKeyManager._log_error("Key登录失败")
            return False
