"""
Telegram 密钥的备份与恢复

把 tdata 目录下的 identity / info / key 三个文件
以 base64 编码存进配置，需要时再写回磁盘来模拟登录状态。
"""
import base64
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Callable

from .config import PathConfig

if TYPE_CHECKING:
    from .service import ConfigService


class TelegramKeyManager:
    """密钥读写逻辑，全部是静态方法，按需调用即可"""

    _log_handler: Optional[Callable[[str], None]] = None

    @classmethod
    def set_log_handler(cls, handler: Optional[Callable[[str], None]]) -> None:
        """注入外部日志处理器，传 None 则清除。"""
        cls._log_handler = handler

    @classmethod
    def _log_error(cls, message: str) -> None:
        """内部用的错误日志，处理器挂了就静默"""
        if cls._log_handler:
            try:
                cls._log_handler(message)
            except Exception:
                pass

    @staticmethod
    def backup_keys(tag: str, folder_path: Path, config_service: 'ConfigService') -> bool:
        """从 tdata 目录读取密钥文件并 base64 编码后存进配置，返回是否备份成功。"""
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
        """把配置里存的密钥写回 tdata 目录实现免密登录，返回是否写入成功。"""
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
