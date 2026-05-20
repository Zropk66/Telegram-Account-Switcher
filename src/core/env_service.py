"""
Telegram 环境探测服务。

负责探测 Telegram 客户端的安装位置，以及扫描本地目录以识别合法的账户文件夹。
"""
import base64
import winreg
from contextlib import suppress
from pathlib import Path
from typing import Dict, Any, Tuple

from src.core.crypto_service import AccountDataCryptoService
from src.core.exceptions import TASException
from src.core.interfaces import IEnvService


class TelegramEnvService(IEnvService):
    """负责 OS 级环境配置读取与账户目录扫描的服务类。"""

    @staticmethod
    def search_client() -> Tuple[str, str]:
        """通过查询注册表 tg:// 协议关联获取 Telegram 客户端的安装路径。 """
        try:
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"tg\shell\open\command")
            command = winreg.QueryValue(key, None)

            exe_path = Path(TelegramEnvService._extract_path(command)).resolve(strict=True)
            if not exe_path.is_file():
                raise TASException("客户端可执行文件不存在。")

            return exe_path.name, str(exe_path.parent)
        except (FileNotFoundError, OSError, AttributeError) as e:
            raise TASException("无法定位 Telegram 客户端，请确保程序已正确安装。") from e

    @staticmethod
    def _extract_path(command: str) -> str:
        """从注册表命令行字符串中提取可执行路径。"""
        if not command:
            raise AttributeError("命令为空")

        if command.startswith('"'):
            end_quote = command.find('"', 1)
            if end_quote != -1:
                return command[1:end_quote]

        return command.split()[0].strip('"\'')

    @staticmethod
    def scan_accounts(base_path: str, passcode: str = None) -> Dict[str, Dict[str, Any]]:
        """扫描目录下的所有有效账户文件夹。"""
        results = {}
        base = Path(base_path)
        if not base.is_dir():
            return results

        feature_files = ['key_datas', 'settingss', 'D877F783D5D3EF8Cs']

        for entry in base.iterdir():
            if not entry.is_dir():
                continue

            if any((entry / f).exists() for f in feature_files) or (entry / 'D877F783D5D3EF8C' / 'maps').exists():
                folder_name = entry.name

                user_id = AccountDataCryptoService.decrypt_account_id(entry, passcode) or ""

                tag_file = entry / "tas_tag"
                tag_name = tag_file.read_text(encoding="utf-8").strip() if tag_file.is_file() else folder_name

                account_data = {
                    'id': user_id,
                    'tag': tag_name,
                    'folder': folder_name,
                    'info': '', 'identity': '', 'key': ''
                }

                def _b64_save(path: Path) -> str:
                    """内部方法：_b64_save。"""
                    with suppress(Exception):
                        return base64.b64encode(path.read_bytes()).decode()
                    return ""

                account_data['info'] = _b64_save(entry / 'D877F783D5D3EF8C' / 'maps')
                account_data['identity'] = _b64_save(entry / 'D877F783D5D3EF8Cs')
                account_data['key'] = _b64_save(entry / 'key_datas')

                results[folder_name] = account_data

        return results
