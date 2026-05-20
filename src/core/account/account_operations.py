"""
账户操作逻辑模块。

这里封装真正触碰账户目录和加密状态的切换动作，调用方只负责决定切换时机。
"""

from contextlib import suppress
from pathlib import Path
from typing import Literal, Callable, Optional

from src.core.account.account_services import find_account_folder, swap_active_tdata_with_target, AccountRecoveryService
from src.core.config import ConfigService
from src.core.crypto import AESCipher
from src.core.exceptions import TASException, TASCipherException
from src.core.logger import Logger
from src.core.process_manager import ProcessManager
from src.core.runtime import delay, generate_temp_name

logger = Logger()
configs = ConfigService()

def restore_default(max_retries: int = 5) -> bool:
    """还原默认账户，并在需要时加密当前活跃账户数据。"""
    return _account_switch("restore", max_retries)


def switch_to_tag(max_retries: int = 5, confirm_callback: Optional[Callable[[str], bool]] = None) -> bool:
    """切换到配置中的目标账户，必要时允许用户确认密钥重构。"""
    return _account_switch("target", max_retries, confirm_callback)


def _account_switch(method: Literal["restore", "target"], max_retries: int = 5,
                    confirm_callback: Optional[Callable[[str], bool]] = None) -> bool:
    """串联目录交换、密钥解密和文件锁重试，保证一次切换要么成功要么明确失败。"""
    cipher = AESCipher(configs.pwd)
    target_tag = None

    for attempt in range(max_retries):
        try:
            target_tag = configs.default if method == "restore" else configs.tag
            use_key_login = getattr(configs, "force_key_login", False)
            tag_folder = find_account_folder(configs.path, target_tag)

            if not use_key_login:
                if not tag_folder:
                    if configs.has_complete_keys(target_tag):
                        if confirm_callback:
                            msg = f"未找到标签 '{target_tag}' 的文件夹，是否使用密钥重构登录？"
                            if confirm_callback(msg):
                                use_key_login = True
                            else:
                                return False
                        else:
                            return False
                    else:
                        if attempt == max_retries - 1:
                            raise TASException(f"未找到标签 '{target_tag}' 的文件或密钥")

            tdata_path = Path(configs.path) / "tdata"

            if use_key_login:
                logger.debug(f"密钥登录: {target_tag}")
                if configs.login_with_keys(target_tag, str(tdata_path)):
                    configs.decrypted = True
                    return True
                return False

            if tag_folder == "tdata":
                try:
                    cipher.decrypt(tdata_path / "key_datas")
                    configs.decrypted = True
                    return True
                except TASCipherException as e:
                    if configs.has_complete_keys(target_tag):
                        if confirm_callback:
                            msg = f"检测到当前账户 '{target_tag}' 密钥损坏，是否尝试从备份库修复?"
                            if confirm_callback(msg):
                                if configs.login_with_keys(target_tag, str(Path(configs.path) / "tdata")):
                                    try:
                                        cipher.decrypt(Path(configs.path) / "tdata" / "key_datas")
                                        configs.decrypted = True
                                        return True
                                    except TASCipherException:
                                        return False
                            else:
                                return False
                    logger.warning(f"解密失败: {e}. 请检查密码是否正确。", popup=True)
                    return False

            method_func = {"restore": switch_to_default, "target": switch_to_target}.get(method)
            if not method_func:
                raise TASException(f"模式 '{method}' 未定义")

            temp = generate_temp_name()
            if method_func(cipher, temp):
                return True

            delay(1)

        except TASCipherException as e:
            logger.error(f"无法解密账户 '{target_tag}': {e}", popup=True)
            return False
        except PermissionError:
            if attempt == max_retries - 1:
                raise TASException("权限不足. 请确保 Telegram 已完全关闭。")
            delay(1)
        except (FileNotFoundError, OSError) as e:
            if attempt == max_retries - 1:
                raise TASException(f"切换失败: {e}")
            delay(1)

    return False


def switch_to_default(cipher: AESCipher, temp: str) -> bool:
    """把默认账户目录提升为活跃 tdata。"""
    tdata_path = Path(configs.path) / "tdata"

    with suppress(FileNotFoundError, TASCipherException, PermissionError):
        if configs.decrypted and configs.tag:
            cipher.encrypt(tdata_path / "key_datas")

    default_folder = find_account_folder(configs.path, configs.default)
    if not default_folder:
        return False

    return swap_active_tdata_with_target(configs.path, default_folder, temp)


def switch_to_target(cipher: AESCipher, temp: str) -> bool:
    """把目标账户目录提升为活跃 tdata，并解密其密钥数据。"""
    folder_name = find_account_folder(configs.path, configs.tag)
    if not folder_name:
        return False

    target_path = Path(configs.path) / folder_name
    tdata_path = Path(configs.path) / "tdata"

    if target_path == tdata_path:
        cipher.decrypt(tdata_path / "key_datas")
        configs.decrypted = True
        return True

    if not swap_active_tdata_with_target(configs.path, folder_name, temp):
        return False

    cipher.decrypt(tdata_path / "key_datas")
    configs.decrypted = True
    return True


def recovery() -> None:
    """严重错误时强制关闭客户端，并尽量恢复默认账户。"""
    pm = ProcessManager()
    with suppress(FileNotFoundError, PermissionError):
        pm.kill_process(configs.client)
        restore_default()
