# -*- coding: utf-8 -*-
# @File ： account_operations.py
# @Time : 2025/8/5 23:45
# @Author : Zropk
import secrets
import shutil
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Literal

from PySide6.QtWidgets import QMessageBox, QApplication

from src.modules.config_manager import ConfigManage
from src.modules.crypto import AESCipher
from src.modules.exceptions import TASException, TASCipherException
from src.modules.utils import search_file_in_dirs


def restore_default(max_retries: int = 5) -> bool:
    """恢复默认账户"""
    return _account_switch("restore", max_retries)


def switch_to_tag(max_retries: int = 5) -> bool:
    """切换至目标标签"""
    return _account_switch("target", max_retries)


def _account_switch(method: Literal["restore", "target"], max_retries: int = 5):
    """底层切换逻辑实现"""
    configs = ConfigManage()
    cipher = AESCipher(configs.pwd)
    target_tag = None

    for attempt in range(max_retries):
        try:
            target_tag = configs.default if method == "restore" else configs.tag
            use_key_login = getattr(configs, "force_key_login", False)

            tag_folder = search_file_in_dirs(configs.path, target_tag)

            if not use_key_login:
                if not tag_folder:
                    if configs.has_complete_keys(target_tag):
                        QApplication.instance() or QApplication(sys.argv)
                        reply = QMessageBox.question(
                            None,
                            "账户切换确认",
                            f"未找到标签 '{target_tag}' 的文件夹，是否使用密钥重构登录？",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if reply == QMessageBox.Yes:
                            use_key_login = True
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
                        Logger().warning(f"")
                        QApplication.instance() or QApplication(sys.argv)
                        reply = QMessageBox.question(
                            None,
                            "提示",
                            f"检测到当前账户 '{target_tag}' 密钥损坏，是否尝试从备份库修复?",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if reply == QMessageBox.Yes:
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

            temp = f"tdata-{''.join(secrets.token_hex(4))}"
            if method_func(configs, cipher, temp):
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
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(1)

    return False


def switch_to_default(configs: ConfigManage, cipher: AESCipher, temp: str):
    """还原默认账户"""
    base_path = Path(configs.path)
    tdata_path = base_path / "tdata"
    key_datas_path = tdata_path / "key_datas"
    temp_path = base_path / temp
    
    with suppress(FileNotFoundError, TASCipherException, PermissionError):
        if configs.decrypted and configs.tag:
            cipher.encrypt(key_datas_path)

    try:
        if tdata_path.exists():
            tdata_path.rename(temp_path)
    except PermissionError:
        return False

    try:
        default_folder = search_file_in_dirs(configs.path, configs.default)
        if default_folder:
            (base_path / default_folder).rename(tdata_path)
            return True
        return False
    except (FileNotFoundError, PermissionError):
        if temp_path.exists():
            with suppress(OSError):
                temp_path.rename(tdata_path)
        return False


def switch_to_target(configs: ConfigManage, cipher: AESCipher, temp: str):
    """切换至目标账户布局"""
    base_path = Path(configs.path)
    tdata_path = base_path / "tdata"
    temp_path = base_path / temp

    try:
        folder_name = search_file_in_dirs(configs.path, configs.tag)
        if not folder_name:
            return False
        target_dir = base_path / folder_name
    except TypeError:
        return False

    key_datas_path = target_dir / "key_datas"
    if target_dir == tdata_path:
        cipher.decrypt(key_datas_path)
        configs.decrypted = True
        return True

    cipher.decrypt(key_datas_path)
    configs.decrypted = True

    try:
        default_folder = search_file_in_dirs(configs.path, configs.default)
        if default_folder:
            (base_path / default_folder).rename(temp_path)
    except FileNotFoundError:
        pass
    except PermissionError:
        return False

    try:
        target_dir.rename(tdata_path)
        return True
    except (FileNotFoundError, PermissionError):
        _rollback_rename(base_path, temp)
        return False


def _rollback_rename(base_path: Path, temp: str):
    """回退重命名操作"""
    try:
        temp_path = base_path / temp
        target_path = base_path / "tdata"

        if target_path.exists():
            if target_path.is_dir():
                shutil.rmtree(target_path)

        if temp_path.exists():
            temp_path.rename(target_path)
    except OSError:
        pass


def recovery():
    """紧急强制恢复"""
    configs = ConfigManage()
    with suppress(FileNotFoundError, PermissionError):
        from src.modules.process_manager import ProcessManager
        ProcessManager.kill_process(configs.client)
        restore_default()
