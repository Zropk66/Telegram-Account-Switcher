import base64
import os
import winreg
from contextlib import suppress
from pathlib import Path
from typing import Dict, Any, Tuple

from src.core.crypto_service import AccountDataCryptoService
from src.core.exceptions import TASException
from src.core.logger import Logger
from src.core.utils import search_file_in_dirs


class TelegramEnvService:
    """探测 Telegram 安装路径和账户信息。"""

    @staticmethod
    def search_client() -> Tuple[str, str]:
        """从注册表的 ``tg://`` 协议关联中提取客户端路径，返回 (可执行文件名, 所在目录)。"""
        try:
            protocol_key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"tg", 0, winreg.KEY_READ)
            with winreg.OpenKey(protocol_key, r"shell\open\command") as command_key:
                command = winreg.QueryValue(command_key, None)
                full_path = Path(TelegramEnvService.extract_executable_path(command)).resolve(strict=True)
                if not full_path or not os.path.exists(full_path):
                    raise TASException('提取的客户端路径无效或文件不存在.')

                client = os.path.basename(full_path)
                path = os.path.dirname(full_path)
                return client, path
        except (FileNotFoundError, AttributeError) as e:
            raise TASException('无法找到客户端，请确保协议关联已安装并注册') from e
        except RuntimeError as e:
            raise TASException(f'注册表操作失败') from e
        except PermissionError as e:
            raise TASException('如果权限不足，请以管理员身份运行该程序') from e
        except OSError as e:
            raise TASException(f'系统错误({e.winerror}): {e.strerror}') from e

    @staticmethod
    def extract_executable_path(command: str) -> str:
        """从注册表的 shell command 字符串中提取可执行文件路径。"""
        if not command:
            raise AttributeError("命令字符串为空")

        try:
            if command.startswith('"'):
                end_quote = command.find('"', 1)
                if end_quote != -1:
                    return command[1:end_quote]

            parts = command.split()
            if parts:
                candidate = parts[0]
                if os.path.exists(candidate):
                    return candidate

                clean_candidate = candidate.strip("\"'")
                if os.path.exists(clean_candidate):
                    return clean_candidate
                return candidate
            return command
        except AttributeError:
            raise

    @staticmethod
    def scan_accounts(base_path: str, passcode: str = None) -> Dict[str, Dict[str, Any]]:
        """
        扫描指定目录下所有 Telegram 账户。

        通过 ``key_datas``、``settingss``、``D877F783D5D3EF8Cs`` 等特征文件
        识别账户文件夹，并尝试解密获取 user_id。
        """
        result: Dict[str, Dict[str, Any]] = {}
        try:
            base = Path(base_path)
            if not base.is_dir():
                return result

            suspected_folders = []
            for entry in base.iterdir():
                if not entry.is_dir():
                    continue

                if (entry / 'key_datas').exists() or \
                        (entry / 'settingss').exists() or \
                        (entry / 'D877F783D5D3EF8Cs').exists() or \
                        (entry / 'D877F783D5D3EF8C' / 'maps').exists():
                    suspected_folders.append(entry)

            for folder in suspected_folders:
                folder_name = folder.name
                user_id = AccountDataCryptoService.decrypt_account_id(folder, passcode) or ""

                tag_name = folder_name
                tas_tag_file = folder / "tas_tag"
                if tas_tag_file.is_file():
                    with suppress(Exception):
                        content = tas_tag_file.read_text(encoding="utf-8").strip()
                        if content:
                            tag_name = content

                account_data = {
                    'id': user_id,
                    'tag': tag_name,
                    'folder': folder_name,
                    'info': '',
                    'identity': '',
                    'key': ''
                }

                # 密钥数据 Base64 编码，用于快速备份/恢复（非深度解密）
                info_path = folder / 'D877F783D5D3EF8C' / 'maps'
                identity_path = folder / 'D877F783D5D3EF8Cs'
                key_path = folder / 'key_datas'

                if info_path.exists():
                    with suppress(Exception):
                        account_data['info'] = base64.b64encode(info_path.read_bytes()).decode()
                if identity_path.exists():
                    with suppress(Exception):
                        account_data['identity'] = base64.b64encode(identity_path.read_bytes()).decode()
                if key_path.exists():
                    with suppress(Exception):
                        account_data['key'] = base64.b64encode(key_path.read_bytes()).decode()

                result[folder_name] = account_data

        except Exception:
            with suppress(Exception):
                Logger().error("扫描账户过程中发生严重异常")

        return result

    @staticmethod
    def sync_account_folders(base_path: str, tags: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], bool]:
        """把配置中的账户文件夹路径和磁盘实际情况对齐，返回 (更新后的 tags, 是否有变化)。"""
        if not base_path or not os.path.isdir(base_path):
            return tags, False

        updated_tags = tags.copy()
        changed = False
        for tag, info in updated_tags.items():
            real_folder = search_file_in_dirs(base_path, tag)
            if real_folder and info.get("folder") != real_folder:
                info["folder"] = real_folder
                changed = True
        return updated_tags, changed
