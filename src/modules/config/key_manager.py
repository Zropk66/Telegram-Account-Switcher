# -*- coding: utf-8 -*-
"""Telegram 密钥管理"""
import base64
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Callable

from .config import PathConfig

if TYPE_CHECKING:
    from .service import ConfigService


class TelegramKeyManager:
    """Telegram 密钥管理逻辑"""

    # 类级别的日志处理器，可通过依赖注入设置
    _log_handler: Optional[Callable[[str], None]] = None

    @classmethod
    def set_log_handler(cls, handler: Optional[Callable[[str], None]]) -> None:
        """
        设置日志处理器（依赖注入入口）

        Args:
            handler: 日志处理函数，签名 (message: str) -> None
                    传入 None 可移除当前处理器
        """
        cls._log_handler = handler

    @classmethod
    def _log_error(cls, message: str) -> None:
        """记录错误，使用依赖注入的日志处理器"""
        if cls._log_handler:
            try:
                cls._log_handler(message)
            except Exception:
                pass  # 如果处理器失败，静默处理

    @staticmethod
    def backup_keys(tag: str, folder_path: Path, config_service: 'ConfigService') -> bool:
        """从文件夹读取密钥并备份到配置中"""
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
            account_data['info'] = base64.b64encode(data_info).decode()
            account_data['identity'] = base64.b64encode(data_identity).decode()
            account_data['key'] = base64.b64encode(data_key).decode()

            config_service.set_account(tag, account_data)
            return True
        except (OSError, ValueError, TypeError):
            return False

    @staticmethod
    def login_with_keys(tag: str, tdata_path: str, config_service: 'ConfigService') -> bool:
        """使用备份的密钥模拟登录状态"""
        if not config_service.has_complete_keys(tag):
            return False

        try:
            account = config_service.get_account(tag)
            if not (account.get('key') and account.get('identity') and account.get('info')):
                return False
            try:
                tdata_dir = Path(tdata_path)
                tdata_dir.mkdir(parents=True, exist_ok=True)

                info_path = PathConfig.get_info_path(tdata_dir, True)
                identity_path = PathConfig.get_identity_path(tdata_dir, True)
                key_path = PathConfig.get_key_path(tdata_dir, True)

                info_path.write_bytes(base64.b64decode(account['info']))
                identity_path.write_bytes(base64.b64decode(account['identity']))
                key_path.write_bytes(base64.b64decode(account['key']))

                return True
            except (OSError, ValueError):
                return False

        except Exception:
            TelegramKeyManager._log_error("Key登录失败")
            return False
