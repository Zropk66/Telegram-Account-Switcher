"""
命令行控制器模块。

通过依赖注入实现业务逻辑与界面展示的解耦，支持账户加密、解密、切换等操作。
"""
import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple, Callable

from src.core import AESCipher
from src.core.config import ConfigService
from src.core.exceptions import TASConfigException
from src.core.logger import Logger
from src.core.utils import search_file_in_dirs

# 回调类型别名
HelpHandler = Callable[[str], None]
SettingsHandler = Callable[[str], None]
InfoHandler = Callable[[str], None]
WarningHandler = Callable[[str], None]
ErrorHandler = Callable[[str], None]


class CLIController:
    """命令行控制器。"""

    def __init__(
            self,
            version: str = "2.0.0",
            config: Optional[ConfigService] = None,
            logger: Optional[Logger] = None,
            cipher_factory: Optional[Callable[[str], AESCipher]] = None,
            help_handler: Optional[HelpHandler] = None,
            settings_handler: Optional[SettingsHandler] = None,
            info_handler: Optional[InfoHandler] = None,
            warning_handler: Optional[WarningHandler] = None,
            error_handler: Optional[ErrorHandler] = None
    ):
        """初始化命令行控制器。"""
        self.version = version
        self.config = config or ConfigService()
        self.logger = logger or Logger()
        self._cipher_factory = cipher_factory or (lambda pwd: AESCipher(pwd))

        self._help_handler = help_handler
        self._settings_handler = settings_handler
        self._info_handler = info_handler
        self._warning_handler = warning_handler
        self._error_handler = error_handler

    @staticmethod
    def parse_args() -> argparse.Namespace:
        """解析命令行参数。"""
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
        """校验运行配置。"""
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
        """应用命令行参数到配置。"""
        if args.password:
            self.config.pwd = args.password

        if args.key_login:
            self.config.force_key_login = True

        if args.switch:
            return self._validate_tag(args.switch)

        return None

    def _validate_tag(self, tag: str) -> str:
        """验证标签有效性。"""
        if tag == self.config.default:
            return tag

        if tag not in self.config.tags or not search_file_in_dirs(self.config.path, tag):
            self.logger.warning(f"标签无效或文件缺失: {tag}")
            return self.config.default
        return tag

    def handle_actions(self, args: argparse.Namespace) -> bool:
        """根据解析结果分发到对应的处理方法。"""
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
        """弹出帮助窗口；无 UI 时降级为控制台输出。"""
        if self._help_handler:
            self._help_handler(self.version)
        else:
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
        """显示版本号。"""
        message = f"TAS v{self.version}"
        if self._info_handler:
            self._info_handler(message)
        else:
            print(message)

    def _open_settings(self) -> None:
        """打开设置窗口。"""
        if self._settings_handler:
            self._settings_handler(self.version)
        else:
            print("设置功能需要UI支持")

    def _process_tags(self, operation: str) -> None:
        """批量处理所有标签的加密或解密操作。"""
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
        """处理单个标签的加密或解密操作。"""
        if not self.config.pwd:
            self._handle_error("未指定密钥.")
            sys.exit()

        if tag not in self.config.tags and tag != self.config.default:
            self._handle_error(f"标签 '{tag}' 未注册.")
            sys.exit()

        if tag == self.config.default:
            self._handle_warning(f"标签 '{tag}' 为默认账户，禁止操作。")
            return

        cipher = self._cipher_factory(self.config.pwd)
        success, reason = self._process_tag(tag, operation, cipher)

        if success:
            op_name = "加密" if operation == "encrypt" else "解密"
            self._handle_info(f"标签 '{tag}' {op_name}成功")
        else:
            if reason == "已加密":
                self._handle_warning(f"标签 '{tag}' 已加密，跳过。")
            else:
                self._handle_error(f"标签 '{tag}' 操作失败: {reason}")

    def _process_tag(self, tag: str, operation: str, cipher: AESCipher) -> Tuple[bool, Optional[str]]:
        """执行单个标签的实际加密或解密操作。"""
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
        """处理普通信息消息。"""
        self.logger.info(message, popup=True)
        if self._info_handler:
            self._info_handler(message)

    def _handle_warning(self, message: str) -> None:
        """处理警告消息。"""
        self.logger.warning(message, popup=True)
        if self._warning_handler:
            self._warning_handler(message)

    def _handle_error(self, message: str) -> None:
        """处理错误消息。"""
        self.logger.error(message, popup=True)
        if self._error_handler:
            self._error_handler(message)
