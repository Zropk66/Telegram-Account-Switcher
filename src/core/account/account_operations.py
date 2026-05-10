import secrets
import time
from contextlib import suppress
from pathlib import Path
from typing import Literal, Callable, Optional

from src.core.account.account_services import AccountFileSystemService
from src.core.config import ConfigService
from src.core.crypto import AESCipher
from src.core.exceptions import TASException, TASCipherException
from src.core.logger import Logger
from src.core.process_manager import ProcessManager


def restore_default(max_retries: int = 5) -> bool:
    """恢复为默认账户，加密当前账户数据并还原 tdata 文件夹。"""
    return _account_switch("restore", max_retries)


def switch_to_tag(max_retries: int = 5, confirm_callback: Optional[Callable[[str], bool]] = None) -> bool:
    """切换到配置中指定的目标账户，支持重试和用户确认回调，返回是否成功。"""
    return _account_switch("target", max_retries, confirm_callback)


def _account_switch(method: Literal["restore", "target"], max_retries: int = 5,
                    confirm_callback: Optional[Callable[[str], bool]] = None) -> bool:
    """账户切换的核心逻辑，处理加密/解密、文件夹交换和密钥恢复，返回操作是否成功。"""
    configs = ConfigService()
    cipher = AESCipher(configs.pwd)
    target_tag = None

    for attempt in range(max_retries):
        try:
            target_tag = configs.default if method == "restore" else configs.tag
            use_key_login = getattr(configs, "force_key_login", False)

            fs_service = AccountFileSystemService(configs.path)
            tag_folder = fs_service.find_account_folder(target_tag)

            # 没找到对应的文件夹，尝试用备份密钥重建
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

            # 用备份密钥直接登录
            if use_key_login:
                if configs.login_with_keys(target_tag, str(tdata_path)):
                    configs.decrypted = True
                    return True
                return False

            # 目标就是当前活跃的 tdata，只需解密
            if tag_folder == "tdata":
                try:
                    cipher.decrypt(tdata_path / "key_datas")
                    configs.decrypted = True
                    return True
                except TASCipherException as e:
                    # 密钥损坏了，看看能不能从备份库修复
                    if configs.has_complete_keys(target_tag):
                        Logger().warning(f"检测到账户 '{target_tag}' 密钥损坏")
                        if confirm_callback:
                            msg = f"检测到当前账户 '{target_tag}' 密钥损坏，是否尝试从备份库修复?"
                            if confirm_callback(msg):
                                if configs.login_with_keys(target_tag, str(Path(configs.path) / "tdata")):
                                    with suppress(TASCipherException):
                                        cipher.decrypt(Path(configs.path) / "tdata" / "key_datas")
                                    configs.decrypted = True
                                    return True
                            else:
                                return False

                    Logger().warning(f"解密当前账户失败: {e}. 请检查密码是否正确。", popup=True)
                    return False

            # 正常的文件夹交换流程
            method_func = {"restore": switch_to_default, "target": switch_to_target}.get(method)
            if not method_func:
                raise TASException(f"模式 '{method}' 未定义")

            temp = f"tdata-{secrets.token_hex(4)}"
            if method_func(configs, cipher, temp, fs_service):
                return True

            time.sleep(1)

        except TASCipherException as e:
            Logger().error(f"无法解密账户 '{target_tag}': {e}. 切换中止。", popup=True)
            return False
        except PermissionError:
            if attempt == max_retries - 1:
                raise TASException("权限不足. 请确保 Telegram 已完全关闭。")
            time.sleep(1)
        except (FileNotFoundError, OSError) as e:
            if attempt == max_retries - 1:
                raise TASException(f"切换失败: {e}")
            time.sleep(1)

    return False


def switch_to_default(configs: ConfigService, cipher: AESCipher, temp: str,
                      fs_service: AccountFileSystemService) -> bool:
    """加密当前账户数据，然后把默认账户的文件夹交换为活跃的 tdata，返回是否成功。"""
    tdata_path = Path(configs.path) / "tdata"

    with suppress(FileNotFoundError, TASCipherException, PermissionError):
        if configs.decrypted and configs.tag:
            cipher.encrypt(tdata_path / "key_datas")

    default_folder = fs_service.find_account_folder(configs.default)
    if not default_folder:
        return False

    return fs_service.swap_active_tdata_with_target(default_folder, temp)


def switch_to_target(configs: ConfigService, cipher: AESCipher, temp: str,
                     fs_service: AccountFileSystemService) -> bool:
    """把目标账户的文件夹交换为活跃的 tdata 并解密，返回是否成功。"""
    folder_name = fs_service.find_account_folder(configs.tag)
    if not folder_name:
        return False

    target_path = Path(configs.path) / folder_name
    tdata_path = Path(configs.path) / "tdata"

    # 目标已经是活跃的 tdata，直接解密就行
    if target_path == tdata_path:
        cipher.decrypt(tdata_path / "key_datas")
        configs.decrypted = True
        return True

    if not fs_service.swap_active_tdata_with_target(folder_name, temp):
        return False

    cipher.decrypt(tdata_path / "key_datas")
    configs.decrypted = True
    return True


def recovery() -> None:
    """紧急恢复：强制结束 Telegram 进程并还原默认账户。"""
    configs = ConfigService()
    with suppress(FileNotFoundError, PermissionError):
        ProcessManager.kill_process(configs.client)
        restore_default()
