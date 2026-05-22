"""
Telegram 运行环境探测。
"""
import base64
import winreg
from contextlib import suppress
from pathlib import Path
from typing import Dict, Any, Tuple

from src.core.constants import (
    TELEGRAM_REG_KEY,
    KEY_FOLDER,
    IDENTITY_FOLDER,
    TELEGRAM_IDENTITY_KEY,
    INFO_SUBFOLDER,
    TAG_FILE
)
from src.core.crypto_service import AccountDataCryptoService
from src.core.exceptions import TASException


class TelegramEnvService:
    """环境检测服务。"""

    @staticmethod
    def search_client() -> Tuple[str, str]:
        """查找客户端路径。"""
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, TELEGRAM_REG_KEY) as key:
                command = winreg.QueryValue(key, None)

            exe_path = Path(TelegramEnvService._extract_path(command)).resolve(strict=True)
            if not exe_path.is_file():
                raise TASException("客户端可执行文件不存在。")

            return exe_path.name, str(exe_path.parent)
        except (FileNotFoundError, OSError, AttributeError) as e:
            raise TASException("无法定位 Telegram 客户端，请确保程序已正确安装。") from e

    @staticmethod
    def _extract_path(command: str) -> str:
        """从命令行提取路径。"""
        if not command:
            raise AttributeError("命令为空")

        if command.startswith('"'):
            end_quote = command.find('"', 1)
            if end_quote != -1:
                return command[1:end_quote]

        return command.split()[0].strip('"\'')

    @staticmethod
    def scan_accounts(base_path: str, passcode: str = None) -> Dict[str, Dict[str, Any]]:
        """扫描所有账户。"""
        results = {}
        base = Path(base_path)
        if not base.is_dir():
            return results

        feature_files = [KEY_FOLDER, 'settingss', IDENTITY_FOLDER]

        for entry in base.iterdir():
            if not entry.is_dir():
                continue

            if any((entry / f).exists() for f in feature_files) or (entry / TELEGRAM_IDENTITY_KEY / INFO_SUBFOLDER).exists():
                folder_name = entry.name

                user_id = AccountDataCryptoService.decrypt_account_id(entry, passcode) or ""

                tag_file = entry / TAG_FILE
                tag_name = folder_name
                if tag_file.is_file():
                    with suppress(Exception):
                        tag_name = tag_file.read_text(encoding="utf-8").strip()

                account_data = {
                    'id': user_id,
                    'tag': tag_name,
                    'folder': folder_name,
                    'info': '', 'identity': '', 'key': ''
                }

                def _b64_save(path: Path) -> str:
                    """Base64编码保存。"""
                    with suppress(Exception):
                        return base64.b64encode(path.read_bytes()).decode()
                    return ""

                account_data['info'] = _b64_save(entry / TELEGRAM_IDENTITY_KEY / INFO_SUBFOLDER)
                account_data['identity'] = _b64_save(entry / IDENTITY_FOLDER)
                account_data['key'] = _b64_save(entry / KEY_FOLDER)

                results[folder_name] = account_data

        return results
