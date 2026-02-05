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

    # 循环重试替代递归，避免栈溢出并更清晰
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
                raise TASException(f"模式 ‘{method}’ 未定义")

            temp = f"tdata-{''.join(random.sample('ABCDEFGH', 8))}"
            if method_func(configs, cipher, temp):
                return True

            # 如果返回 False，说明遇到了 PermissionError 但被 catch 了
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
    try:
        path = configs.path
        with suppress(FileNotFoundError, TASCipherException):
            if configs.decrypted:
                cipher.encrypt(os.path.join(path, "tdata", "key_datas"))
            elif configs.has_backup:
                shutil.move(
                    os.path.join(path, "tdata", "key_datas.bak"),
                    os.path.join(path, "tdata", "key_datas"),
                )
            os.rename(os.path.join(path, "tdata"), os.path.join(path, temp))

        os.rename(
            os.path.join(path, search_file_in_dirs(path, configs.default)),
            os.path.join(path, "tdata"),
        )
        return True
    except PermissionError:
        return False


def switch_to_target(configs: ConfigManage, cipher: AESCipher, temp: str):
    """切换为目标账户"""
    try:
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
        os.rename(
            os.path.join(path, search_file_in_dirs(path, configs.default)),
            os.path.join(path, temp),
        )
        os.rename(target_dir, os.path.join(path, "tdata"))
        return True
    except PermissionError:
        return False


def recovery():
    """强制恢复为默认账户"""
    configs = ConfigManage()
    with suppress(FileNotFoundError, PermissionError):
        from src.modules.process_manager import ProcessManager

        ProcessManager.kill_process(configs.client)
        # kill_process 现在会等待进程退出，所以不需要额外的 sleep
        account_switch("restore")
