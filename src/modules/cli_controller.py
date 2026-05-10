# -*- coding: utf-8 -*-
import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple

from src.modules import ConfigManage, AESCipher, Logger
from src.ui.help_ui import open_help_window
from src.ui.settings_ui import open_settings_window


class CLIController:
    """CLI 命令处理"""

    def __init__(self, version: str = "1.3.0"):
        self.version = version
        self.config = ConfigManage()
        self.logger = Logger()

        try:
            from src.main import search_file_in_dirs
            self.search_file_in_dirs = staticmethod(search_file_in_dirs)
        except ImportError:
            from src.modules.utils import search_file_in_dirs
            self.search_file_in_dirs = staticmethod(search_file_in_dirs)

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
                from src.modules.exceptions import TASConfigException
                raise TASConfigException("找不到客户端程序")
            if not path.is_dir():
                from src.modules.exceptions import TASConfigException
                raise TASConfigException("路径格式不正确")
            if not self.config.default:
                from src.modules.exceptions import TASConfigException
                raise TASConfigException("未设置默认账户")
            if not self.search_file_in_dirs(str(path), self.config.default):
                from src.modules.exceptions import TASConfigException
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

        if tag not in self.config.tags or not self.search_file_in_dirs(self.config.path, tag):
            self.logger.warning(f"标签无效或文件缺失: {tag}")
            return self.config.default
        return tag

    def handle_actions(self, args: argparse.Namespace) -> bool:
        if args.help:
            open_help_window(self.version)
        elif args.version:
            self.logger.info(f"TAS v{self.version}", popup=True)
        elif args.settings:
            open_settings_window(self.version)
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

    def _process_tags(self, operation: str) -> None:
        if not self.config.pwd:
            self.logger.error("未指定密钥.", popup=True)
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

        self.logger.info(msg, popup=True)

    def _process_single_tag(self, tag: str, operation: str) -> None:
        if not self.config.pwd:
            self.logger.error("未指定密钥.", popup=True)
            sys.exit()

        if tag not in self.config.tags and tag != self.config.default:
            self.logger.error(f"标签 '{tag}' 未注册.", popup=True)
            sys.exit()

        if tag == self.config.default:
            self.logger.warning(f"标签 '{tag}' 为默认账户，禁止操作。", popup=True)
            return

        cipher = AESCipher(self.config.pwd)
        success, reason = self._process_tag(tag, operation, cipher)

        if success:
            self.logger.info(f"标签 '{tag}' {'加密' if operation == 'encrypt' else '解密'}成功", popup=True)
        else:
            if reason == "已加密":
                self.logger.warning(f"标签 '{tag}' 已加密，跳过。", popup=True)
            else:
                self.logger.error(f"标签 '{tag}' 操作失败: {reason}", popup=True)

    def _process_tag(self, tag: str, operation: str, cipher: AESCipher) -> Tuple[bool, Optional[str]]:
        tag_path = self.search_file_in_dirs(self.config.path, tag)
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
