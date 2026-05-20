"""Telegram 密钥的备份与恢复，通过 base64 编码存储密钥文件实现免密登录。"""

import base64
from pathlib import Path
from typing import Optional, Callable

from src.core.interfaces import IKeyManager, IConfigProvider
from .config import PathConfig


class TelegramKeyManager(IKeyManager):
    """Telegram 账户密钥的备份和恢复，所有方法均为静态方法。"""

    _log_handler: Optional[Callable[[str], None]] = None

    @classmethod
    def set_log_handler(cls, handler: Optional[Callable[[str], None]]) -> None:
        """设置日志处理器，传入 None 则清除。"""
        cls._log_handler = handler

    @classmethod
    def _log_error(cls, message: str) -> None:
        """通过 _log_handler 输出错误日志，处理器异常时静默忽略。"""
        if cls._log_handler:
            try:
                cls._log_handler(message)
            except (RuntimeError, TypeError):
                pass

    @staticmethod
    def backup_keys(tag: str, folder_path: Path, config_service: IConfigProvider) -> bool:
        """从 tdata 目录读取密钥文件，base64 编码后存入配置。"""
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
    def login_with_keys(tag: str, tdata_path: str, config_service: IConfigProvider) -> bool:
        """从配置中读取密钥，解码后写入 tdata 目录实现免密登录。"""
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

        except (OSError, RuntimeError):
            TelegramKeyManager._log_error("Key登录失败")
            return False
