"""命令行控制器."""

import argparse
import sys
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Tuple

from src.core import AESCipher
from src.core.config import ConfigService
from src.core.constants import APP_TITLE, APP_VERSION, KEY_FOLDER
from src.core.exceptions import TASConfigException
from src.core.logger import Logger
from src.core.utils import search_file_in_dirs


class CLIAction(Enum):
    """命令行操作类型."""

    CONTINUE = "continue"  # 无 CLI 操作，继续主流程
    EXIT = "exit"  # 已处理 CLI 操作，安全退出
    SHOW_HELP = "show_help"  # 需展示帮助界面
    SHOW_SETTINGS = "show_settings"  # 需展示设置界面


class CLIController:
    """命令行控制器."""

    def __init__(
        self,
        version: str = APP_VERSION,
        config: Optional[ConfigService] = None,
        logger: Optional[Logger] = None,
        cipher_factory: Optional[Callable[[str], AESCipher]] = None,
    ) -> None:
        """初始化命令行控制器."""
        self.version = version
        self.config = config or ConfigService()
        self.logger = logger or Logger()
        self._cipher_factory = cipher_factory or (lambda pwd: AESCipher(pwd))

    @staticmethod
    def parse_args() -> argparse.Namespace:
        """解析命令行参数."""
        parser = argparse.ArgumentParser(description=f"{APP_TITLE} CLI", add_help=False, exit_on_error=False)

        action_group = parser.add_argument_group()
        action_group.add_argument("--encrypt", "-e", action="store_true", help="加密账户")
        action_group.add_argument("--decrypt", "-d", action="store_true", help="解密账户")
        action_group.add_argument("--switch", "-s", type=str, metavar="tag", help="切换至指定标签账户")
        action_group.add_argument("--key-login", "-k", action="store_true", help="强制Key登录")
        action_group.add_argument("--tag", "-t", type=str, metavar="tag", help="操作指定标签")

        exclusive_group = parser.add_mutually_exclusive_group()
        exclusive_group.add_argument("--version", "-v", action="store_true", help="查看版本")
        exclusive_group.add_argument("--settings", "-c", action="store_true", help="打开设置")
        exclusive_group.add_argument("--help", "-h", action="store_true", help="查看帮助")
        parser.add_argument("--password", "-p", type=str, metavar="password", help="指定解密密钥")

        return parser.parse_args()

    def check_config(self, args: argparse.Namespace) -> bool:
        """校验运行配置."""
        try:
            self.config.sync_all_account_paths()

            tag = self._apply_args(args)
            if tag:
                self.config.tag = tag

            path = Path(self.config.path)

            if not (path / self.config.client).is_file():
                raise TASConfigException("找不到客户端程序")
            if not path.is_dir():
                raise TASConfigException("路径格式不正确")
            if not self.config.default:
                raise TASConfigException("未设置默认账户")
            default_folder = self.config.get_account(self.config.default).get("folder")
            if default_folder and (path / default_folder).is_dir():
                pass
            elif not search_file_in_dirs(str(path), self.config.default):
                raise TASConfigException(f"默认账户 '{self.config.default}' 文件夹未找到")

            return True
        except Exception as e:
            self.logger.exception(f"配置验证失败: {e}", e, popup=True)
            return False

    def _apply_args(self, args: argparse.Namespace) -> Optional[str]:
        """应用命令行参数到配置."""
        if args.password:
            self.config.pwd = args.password

        if args.key_login:
            self.config.force_key_login = True

        if args.switch:
            return self._validate_tag(args.switch)

        return None

    def _validate_tag(self, tag: str) -> str:
        """验证标签有效性."""
        if tag == self.config.default:
            return tag

        if tag not in self.config.tags:
            self.logger.warning(f"标签无效: {tag}")
            return self.config.default

        folder = self.config.get_account(tag).get("folder")
        if folder and (Path(self.config.path) / folder).is_dir():
            return tag

        if not search_file_in_dirs(self.config.path, tag):
            self.logger.warning(f"标签无效或文件缺失: {tag}")
            return self.config.default
        return tag

    def handle_actions(self, args: argparse.Namespace) -> CLIAction:
        """根据解析结果返回执行意图."""
        if args.help:
            return CLIAction.SHOW_HELP
        elif args.version:
            self.logger.info(f"TAS v{self.version}", popup=True)
            return CLIAction.EXIT
        elif args.settings:
            return CLIAction.SHOW_SETTINGS

        if args.encrypt:
            if args.tag:
                self._process_single_tag(args.tag, "encrypt")
            else:
                self._process_tags("encrypt")
            return CLIAction.EXIT
        elif args.decrypt:
            if args.tag:
                self._process_single_tag(args.tag, "decrypt")
            else:
                self._process_tags("decrypt")
            return CLIAction.EXIT

        return CLIAction.CONTINUE

    def _process_tags(self, operation: str) -> None:
        """批量处理所有标签的加密或解密操作."""
        if not self.config.pwd:
            self._handle_error("未指定密钥.")
            sys.exit()

        cipher = self._cipher_factory(self.config.pwd)
        op_name = "加密" if operation == "encrypt" else "解密"

        processed, skipped, failed = [], [], []

        for tag in self.config.tags:
            if tag == self.config.default:
                skipped.append(tag)
                continue

            success, reason = self._process_tag(tag, operation, cipher)
            if success:
                processed.append(tag)
            elif reason == "已加密":
                skipped.append(tag)
            else:
                failed.append((tag, reason))

        if failed:
            msg = f"操作失败: {failed}"
        elif skipped and not processed:
            msg = f"标签均已{op_name}，跳过: {skipped}"
        elif not processed:
            msg = f"所有标签均已{op_name}"
        else:
            msg = f"本次{op_name}的标签 -> {processed}"
            if skipped:
                msg += f" (已跳过: {skipped})"

        self._handle_info(msg)

    def _process_single_tag(self, tag: str, operation: str) -> None:
        """处理单个标签的加密或解密操作."""
        if not self.config.pwd:
            self._handle_error("未指定密钥.")
            sys.exit()

        if tag not in self.config.tags and tag != self.config.default:
            self._handle_error(f"标签 '{tag}' 未注册.")
            sys.exit()

        if tag == self.config.default:
            self._handle_warning(f"标签 '{tag}' 为默认账户，禁止操作.")
            return

        cipher = self._cipher_factory(self.config.pwd)
        success, reason = self._process_tag(tag, operation, cipher)

        if success:
            op_name = "加密" if operation == "encrypt" else "解密"
            self._handle_info(f"标签 '{tag}' {op_name}成功")
        else:
            if reason == "已加密":
                self._handle_warning(f"标签 '{tag}' 已加密，跳过.")
            else:
                self._handle_error(f"标签 '{tag}' 操作失败: {reason}")

    def _process_tag(self, tag: str, operation: str, cipher: AESCipher) -> Tuple[bool, Optional[str]]:
        """执行单个标签的实际加密或解密操作."""
        tag_path = self.config.get_account(tag).get("folder")
        if not tag_path or not (Path(self.config.path) / tag_path).is_dir():
            tag_path = search_file_in_dirs(self.config.path, tag)
            if not tag_path:
                return False, f"标签 '{tag}' 文件缺失"

        key_datas_path = Path(self.config.path) / tag_path / KEY_FOLDER

        if not key_datas_path.exists():
            return False, f"{KEY_FOLDER} 文件不存在"

        try:
            if operation == "encrypt":
                if AESCipher.is_encrypted(key_datas_path):
                    return False, "已加密"
                cipher.encrypt(key_datas_path)
                self.config.backup_account_keys(tag, key_datas_path.parent)
            else:
                cipher.decrypt(key_datas_path)
                self.config.backup_account_keys(tag, key_datas_path.parent)
            return True, None
        except Exception as e:
            return False, str(e)

    def _handle_info(self, message: str) -> None:
        """处理普通信息消息."""
        self.logger.info(message, popup=True)

    def _handle_warning(self, message: str) -> None:
        """处理警告消息."""
        self.logger.warning(message, popup=True)

    def _handle_error(self, message: str) -> None:
        """处理错误消息."""
        self.logger.error(message, popup=True)
