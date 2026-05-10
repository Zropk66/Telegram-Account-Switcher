# -*- coding: utf-8 -*-
# @File ： account_operations.py
# @Time : 2025/8/5 23:45
# @Author : Zropk
import secrets
import time
from contextlib import suppress
from pathlib import Path
from typing import Literal, Callable, Optional

from src.modules.account.account_services import AccountFileSystemService
from src.modules.config_manager import ConfigManage
from src.modules.crypto import AESCipher
from src.modules.exceptions import TASException, TASCipherException


def restore_default(max_retries: int = 5) -> bool:
    """恢复默认账户"""
    return _account_switch("restore", max_retries)


def switch_to_tag(max_retries: int = 5, confirm_callback: Optional[Callable[[str], bool]] = None) -> bool:
    """
    切换至目标标签
    :param max_retries: 最大重试次数
    :param confirm_callback: 确认回调函数，接收提示信息，返回布尔值
    """
    return _account_switch("target", max_retries, confirm_callback)


def _account_switch(method: Literal["restore", "target"], max_retries: int = 5,
                   confirm_callback: Optional[Callable[[str], bool]] = None):
    """底层切换逻辑实现"""
    configs = ConfigManage()
    cipher = AESCipher(configs.pwd)
    target_tag = None

    for attempt in range(max_retries):
        try:
            target_tag = configs.default if method == "restore" else configs.tag
            use_key_login = getattr(configs, "force_key_login", False)

            fs_service = AccountFileSystemService(configs.path)
            tag_folder = fs_service.find_account_folder(target_tag)

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

            if use_key_login:
                if configs.login_with_keys(target_tag, str(Path(configs.path) / "tdata")):
                    configs.decrypted = True
                    return True
                return False

            if tag_folder == "tdata":
                try:
                    cipher.decrypt(Path(configs.path) / "tdata" / "key_datas")
                    configs.decrypted = True
                    return True
                except TASCipherException as e:
                    from src.modules import Logger
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

            method_func = {"restore": switch_to_default, "target": switch_to_target}.get(method)
            if not method_func:
                raise TASException(f"模式 '{method}' 未定义")

            temp = f"tdata-{secrets.token_hex(4)}"
            if method_func(configs, cipher, temp, fs_service):
                return True

            time.sleep(1)

        except TASCipherException as e:
            from src.modules import Logger
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


def switch_to_default(configs: ConfigManage, cipher: AESCipher, temp: str, fs_service: AccountFileSystemService):
    """还原默认账户"""
    tdata_path = Path(configs.path) / "tdata"

    with suppress(FileNotFoundError, TASCipherException, PermissionError):
        if configs.decrypted and configs.tag:
            cipher.encrypt(tdata_path / "key_datas")

    default_folder = fs_service.find_account_folder(configs.default)
    if not default_folder:
        return False

    return fs_service.swap_active_tdata_with_target(default_folder, temp)


def switch_to_target(configs: ConfigManage, cipher: AESCipher, temp: str, fs_service: AccountFileSystemService):
    """切换至目标账户布局"""
    folder_name = fs_service.find_account_folder(configs.tag)
    if not folder_name:
        return False

    target_path = Path(configs.path) / folder_name
    tdata_path = Path(configs.path) / "tdata"

    if target_path == tdata_path:
        cipher.decrypt(tdata_path / "key_datas")
        configs.decrypted = True
        return True

    if not fs_service.swap_active_tdata_with_target(folder_name, temp):
        return False

    cipher.decrypt(tdata_path / "key_datas")
    configs.decrypted = True
    return True


def recovery():
    """紧急强制恢复"""
    configs = ConfigManage()
    with suppress(FileNotFoundError, PermissionError):
        from src.modules.process_manager import ProcessManager
        ProcessManager.kill_process(configs.client)
        restore_default()
