# -*- coding: utf-8 -*-
import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple, Callable

from src.modules.config import ConfigService
from src.modules import AESCipher, Logger
from src.modules.exceptions import TASConfigException
from src.modules.utils import search_file_in_dirs


# 定义回调类型别名，提高代码可读性
HelpHandler = Callable[[str], None]           # (version: str) -> None
SettingsHandler = Callable[[str], None]       # (version: str) -> None
InfoHandler = Callable[[str], None]           # (message: str) -> None
WarningHandler = Callable[[str], None]        # (message: str) -> None
ErrorHandler = Callable[[str], None]          # (message: str) -> None


class CLIController:
    """CLI 命令处理
    
    通过依赖注入接收UI回调，实现业务逻辑与界面展示的解耦。
    
    Args:
        version: 应用程序版本号
        help_handler: 显示帮助窗口的回调函数
        settings_handler: 显示设置窗口的回调函数
        info_handler: 显示信息提示的回调函数（可选）
        warning_handler: 显示警告提示的回调函数（可选）
        error_handler: 显示错误提示的回调函数（可选）
    """

    def __init__(
        self,
        version: str = "1.3.0",
        help_handler: Optional[HelpHandler] = None,
        settings_handler: Optional[SettingsHandler] = None,
        info_handler: Optional[InfoHandler] = None,
        warning_handler: Optional[WarningHandler] = None,
        error_handler: Optional[ErrorHandler] = None
    ):
        self.version = version
        self.config = ConfigService()
        self.logger = Logger()
        
        # 注入的回调函数
        self._help_handler = help_handler
        self._settings_handler = settings_handler
        self._info_handler = info_handler
        self._warning_handler = warning_handler
        self._error_handler = error_handler

    def parse_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="TAS CLI", add_help=False, exit_on_error=False)

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
            if not search_file_in_dirs(str(path), self.config.default):
                raise TASConfigException(f"默认账户 '{self.config.default}' 文件夹未找到")

            return True
        except Exception as e:
            self.logger.exception(f"配置验证失败: {e}", e, popup=True)
            return False

    def _apply_args(self, args: argparse.Namespace) -> Optional[str]:
        if args.password:
            self.config.pwd = args.password

        if args.key_login:
            self.config.force_key_login = True

        if args.switch:
            return self._validate_tag(args.switch)

        return None

    def _validate_tag(self, tag: str) -> str:
        if tag == self.config.default:
            return tag

        if tag not in self.config.tags or not search_file_in_dirs(self.config.path, tag):
            self.logger.warning(f"标签无效或文件缺失: {tag}")
            return self.config.default
        return tag

    def handle_actions(self, args: argparse.Namespace) -> bool:
        """处理命令行动作
        
        根据参数执行相应操作，通过回调函数与UI交互。
        """
        if args.help:
            self._show_help()
        elif args.version:
            self._show_version()
        elif args.settings:
            self._open_settings()
        else:
            if args.encrypt:
                if args.tag:
                    self._process_single_tag(args.tag, "encrypt")
                else:
                    self._process_tags("encrypt")
            elif args.decrypt:
                if args.tag:
                    self._process_single_tag(args.tag, "decrypt")
                else:
                    self._process_tags("decrypt")
            else:
                return False
        return True

    def _show_help(self) -> None:
        """显示帮助窗口"""
        if self._help_handler:
            self._help_handler(self.version)
        else:
            # 降级处理：打印到控制台
            print(f"TAS v{self.version}")
            print("用法: tas [选项]")
            print("选项:")
            print("  -h, --help      显示帮助")
            print("  -v, --version   显示版本")
            print("  -c, --settings  打开设置")
            print("  -e, --encrypt   加密账户")
            print("  -d, --decrypt   解密账户")
            print("  -s, --switch    切换账户")

    def _show_version(self) -> None:
        """显示版本信息"""
        message = f"TAS v{self.version}"
        if self._info_handler:
            self._info_handler(message)
        else:
            print(message)

    def _open_settings(self) -> None:
        """打开设置窗口"""
        if self._settings_handler:
            self._settings_handler(self.version)
        else:
            # 降级处理
            print("设置功能需要UI支持")

    def _process_tags(self, operation: str) -> None:
        if not self.config.pwd:
            self._handle_error("未指定密钥.")
            sys.exit()

        cipher = AESCipher(self.config.pwd)
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
        if not self.config.pwd:
            self._handle_error("未指定密钥.")
            sys.exit()

        if tag not in self.config.tags and tag != self.config.default:
            self._handle_error(f"标签 '{tag}' 未注册.")
            sys.exit()

        if tag == self.config.default:
            self._handle_warning(f"标签 '{tag}' 为默认账户，禁止操作。")
            return

        cipher = AESCipher(self.config.pwd)
        success, reason = self._process_tag(tag, operation, cipher)

        if success:
            self._handle_info(f"标签 '{tag}' {'加密' if operation == 'encrypt' else '解密'}成功")
        else:
            if reason == "已加密":
                self._handle_warning(f"标签 '{tag}' 已加密，跳过。")
            else:
                self._handle_error(f"标签 '{tag}' 操作失败: {reason}")

    def _process_tag(self, tag: str, operation: str, cipher: AESCipher) -> Tuple[bool, Optional[str]]:
        tag_path = search_file_in_dirs(self.config.path, tag)
        if not tag_path:
            return False, f"标签 '{tag}' 文件缺失"

        key_datas_path = Path(self.config.path) / tag_path / "key_datas"

        if not key_datas_path.exists():
            return False, "key_datas 文件不存在"

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
        """处理信息提示"""
        self.logger.info(message, popup=True)
        if self._info_handler:
            self._info_handler(message)

    def _handle_warning(self, message: str) -> None:
        """处理警告提示"""
        self.logger.warning(message, popup=True)
        if self._warning_handler:
            self._warning_handler(message)

    def _handle_error(self, message: str) -> None:
        """处理错误提示"""
        self.logger.error(message, popup=True)
        if self._error_handler:
            self._error_handler(message)
