"""文件夹交换及加解密操作."""

from pathlib import Path
from typing import Callable, Literal, Optional

from src.core.account.account_services import find_account_folder, swap_active_tdata_with_target
from src.core.config import ConfigService
from src.core.constants import KEY_FOLDER, MAX_RETRIES, TDATA_DIR
from src.core.crypto import AESCipher
from src.core.exceptions import TASCipherException, TASException
from src.core.logger import Logger
from src.core.process_manager import ProcessManager
from src.core.runtime import delay, generate_temp_name

logger = Logger()
configs = ConfigService()


def restore_default(
    max_retries: int = MAX_RETRIES, target_folder: Optional[str] = None, temp_name: Optional[str] = None
) -> bool:
    """还原默认账户."""
    return _account_switch("restore", max_retries, target_folder=target_folder, temp_name=temp_name)


def switch_to_tag(
    max_retries: int = MAX_RETRIES,
    confirm_callback: Optional[Callable[[str], bool]] = None,
    target_folder: Optional[str] = None,
    temp_name: Optional[str] = None,
) -> bool:
    """切换到指定标签账户."""
    return _account_switch("target", max_retries, confirm_callback, target_folder, temp_name)


def _account_switch(
    method: Literal["restore", "target"],
    max_retries: int = MAX_RETRIES,
    confirm_callback: Optional[Callable[[str], bool]] = None,
    target_folder: Optional[str] = None,
    temp_name: Optional[str] = None,
) -> bool:
    """执行账户切换流程."""
    cipher = AESCipher(configs.pwd)
    target_tag = None

    for attempt in range(max_retries):
        try:
            target_tag = configs.default if method == "restore" else configs.tag
            use_key_login = getattr(configs, "force_key_login", False)
            tag_folder = target_folder or find_account_folder(configs.path, target_tag)

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

            tdata_path = Path(configs.path) / TDATA_DIR

            if use_key_login:
                logger.debug(f"密钥登录: {target_tag}")
                if configs.login_with_keys(target_tag, str(tdata_path)):
                    configs.decrypted = True
                    return True
                return False

            if tag_folder == TDATA_DIR:
                try:
                    cipher.decrypt(tdata_path / KEY_FOLDER)
                    configs.decrypted = True
                    return True
                except TASCipherException as e:
                    if configs.has_complete_keys(target_tag):
                        if confirm_callback:
                            msg = f"检测到当前账户 '{target_tag}' 密钥损坏，是否尝试从备份库修复?"
                            if confirm_callback(msg):
                                if configs.login_with_keys(target_tag, str(Path(configs.path) / TDATA_DIR)):
                                    try:
                                        cipher.decrypt(Path(configs.path) / TDATA_DIR / KEY_FOLDER)
                                        configs.decrypted = True
                                        return True
                                    except TASCipherException:
                                        return False
                            else:
                                return False
                    logger.warning(f"解密失败: {e}. 请检查密码是否正确.", popup=True)
                    return False

            method_func = {"restore": switch_to_default, "target": switch_to_target}.get(method)
            if not method_func:
                raise TASException(f"模式 '{method}' 未定义")

            temp = temp_name or generate_temp_name()
            if method_func(cipher, temp, tag_folder):
                return True

            delay(0.1)

        except TASCipherException as e:
            logger.error(f"无法解密账户 '{target_tag}': {e}", popup=True)
            return False
        except PermissionError:
            if attempt == max_retries - 1:
                raise TASException("权限不足. 请确保 Telegram 已完全关闭.")
            delay(0.1)
        except (FileNotFoundError, OSError) as e:
            if attempt == max_retries - 1:
                raise TASException(f"切换失败: {e}")
            delay(0.1)

    return False


def switch_to_default(cipher: AESCipher, temp: str, target_folder: Optional[str] = None) -> bool:
    """切换到默认账户."""
    tdata_path = Path(configs.path) / TDATA_DIR

    if configs.pwd and configs.decrypted and configs.tag:
        try:
            cipher.encrypt(tdata_path / KEY_FOLDER)
        except FileNotFoundError as e:
            logger.warning(f"加密当前活跃账户数据时未找到 key_datas 文件: {e}")
        except (TASCipherException, PermissionError) as e:
            logger.error(f"加密当前活跃账户数据失败: {e}")

    default_folder = target_folder or find_account_folder(configs.path, configs.default)
    if not default_folder:
        default_info = configs.get_account(configs.default)
        if default_info and default_info.get("folder"):
            default_folder = default_info["folder"]

    if not default_folder:
        logger.error(f"无法定位默认账户 '{configs.default}' 的文件夹")
        return False

    return swap_active_tdata_with_target(configs.path, default_folder, temp)


def switch_to_target(cipher: AESCipher, temp: str, target_folder: Optional[str] = None) -> bool:
    """切换到目标账户."""
    folder_name = target_folder or find_account_folder(configs.path, configs.tag)
    if not folder_name:
        return False

    target_path = Path(configs.path) / folder_name
    tdata_path = Path(configs.path) / TDATA_DIR

    if target_path == tdata_path:
        cipher.decrypt(tdata_path / KEY_FOLDER)
        configs.decrypted = True
        return True

    if not swap_active_tdata_with_target(configs.path, folder_name, temp):
        return False

    cipher.decrypt(tdata_path / KEY_FOLDER)
    configs.decrypted = True
    return True


def recovery(config: Optional[ConfigService] = None, logger: Optional[Logger] = None) -> None:
    """紧急恢复默认账户."""
    pm = ProcessManager()
    cfg = config or configs
    log = logger or globals().get("logger")
    try:
        pm.kill_process(cfg.client)
        restore_default()
    except Exception as e:
        if log:
            log.error(f"紧急恢复执行中发生异常: {e}")
