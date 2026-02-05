# -*- coding: utf-8 -*-
# @File ： account_operations.py
# @Time : 2025/8/5 23:45
# @Author : Zropk
import os
import random
import shutil
import time
from contextlib import suppress
from pathlib import Path
from typing import Literal

from src.modules.utils import search_file_in_dirs
from src.modules.process_manager import ProcessManager
from src.modules.aes_crypto import AESCipher
from src.modules.config_manager import ConfigManage
from src.modules.exceptions import TASException, TASCipherException


def account_switch(
        method: Literal["restore", "target"],
        tag_in_folder: bool = False,
        max_retries: int = 5,
):
    """控制账户的切换与还原"""
    configs = ConfigManage()
    cipher = AESCipher(configs.pwd)

    for attempt in range(max_retries):
        try:
            if tag_in_folder:
                with suppress(TASCipherException):
                    tag_path = Path(configs.path) / search_file_in_dirs(
                        configs.path, configs.tag
                    )
                    cipher.decrypt(tag_path / "key_datas")
                    configs.decrypted = True
                    return ProcessManager.start_process(configs)

            method_func = {
                "restore": switch_to_default,
                "target": switch_to_target,
            }.get(method)

            if not method_func:
                raise TASException(f"模式 '{method}' 未定义")

            # 每次重试生成新的临时文件夹名称
            temp = f"tdata-{''.join(random.sample('ABCDEFGH', 8))}"
            if method_func(configs, cipher, temp):
                return True

            time.sleep(1)

        except PermissionError:
            if attempt == max_retries - 1:
                raise TASException(
                    "权限不足，账户切换失败. 请确保 Telegram 已完全关闭。"
                )
            time.sleep(1)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(1)

    return False


def switch_to_default(configs: ConfigManage, cipher: AESCipher, temp: str):
    """切换回默认账户"""
    path = configs.path
    with suppress(FileNotFoundError, TASCipherException, PermissionError):
        # 尝试备份或加密当前tdata
        if configs.decrypted:
            cipher.encrypt(os.path.join(path, "tdata", "key_datas"))
        elif configs.has_backup:
            shutil.move(
                os.path.join(path, "tdata", "key_datas.bak"),
                os.path.join(path, "tdata", "key_datas"),
            )

    try:
        # 重命名当前tdata为临时名称
        os.rename(os.path.join(path, "tdata"), os.path.join(path, temp))
    except FileNotFoundError:
        pass
    except PermissionError:
        return False

    try:
        # 重命名默认账户为tdata
        os.rename(
            os.path.join(path, search_file_in_dirs(path, configs.default)),
            os.path.join(path, "tdata"),
        )
        return True
    except FileNotFoundError:
        # 恢复原始tdata
        if os.path.exists(os.path.join(path, temp)):
            with suppress(OSError):
                os.rename(os.path.join(path, temp), os.path.join(path, "tdata"))
        return False
    except PermissionError:
        # 尝试回滚
        if os.path.exists(os.path.join(path, temp)):
            with suppress(OSError):
                os.rename(os.path.join(path, temp), os.path.join(path, "tdata"))
        return False


def switch_to_target(configs: ConfigManage, cipher: AESCipher, temp: str):
    """切换为目标账户"""
    path = configs.path

    try:
        target_dir = Path(path) / search_file_in_dirs(path, configs.tag)
    except TypeError:
        return False

    if target_dir == os.path.join(path, "tdata"):
        return True

    try:
        cipher.decrypt(os.path.join(target_dir, "key_datas"))
        configs.decrypted = True
    except TASCipherException:
        shutil.copy2(
            os.path.join(target_dir, "key_datas"),
            os.path.join(target_dir, "key_datas.bak"),
        )
        configs.has_backup = True

    try:
        # 重命名当前tdata为临时名称
        os.rename(
            os.path.join(path, search_file_in_dirs(path, configs.default)),
            os.path.join(path, temp),
        )
    except FileNotFoundError:
        pass  # 可能是首次切换
    except PermissionError:
        return False

    try:
        # 重命名目标账户为tdata
        os.rename(target_dir, os.path.join(path, "tdata"))
        return True
    except (FileNotFoundError, PermissionError):
        # 尝试回滚
        _rollback_rename(path, configs.default, temp)
        return False


def _rollback_rename(path: str, default_tag: str, temp: str):
    """回滚重命名操作"""
    try:
        # 尝试恢复原始tdata
        temp_path = os.path.join(path, temp)
        default_path = os.path.join(path, search_file_in_dirs(path, default_tag))
        target_path = os.path.join(path, "tdata")

        if os.path.exists(target_path):
            if os.path.isdir(target_path):
                shutil.rmtree(target_path)

        # 恢复临时文件夹
        if os.path.exists(temp_path):
            os.rename(temp_path, target_path)
    except OSError:
        pass  # 回滚失败，状态已损坏


def recovery():
    """强制恢复为默认账户"""
    configs = ConfigManage()
    with suppress(FileNotFoundError, PermissionError):
        from src.modules.process_manager import ProcessManager
        ProcessManager.kill_process(configs.client)
        account_switch("restore")
