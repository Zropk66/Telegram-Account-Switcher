"""配置服务."""

import os
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from src.core.config.data import ConfigData
from src.core.config.key_manager import TelegramKeyManager
from src.core.config.runtime import RuntimeState
from src.core.config.storage import ConfigStorage
from src.core.constants import LaunchMode, TELEGRAM_EXE
from src.core.utils import format_timedelta

T = TypeVar("T")


class ConfigService:
    """配置服务."""

    _DEFAULT_CONFIG = {
        "client": TELEGRAM_EXE,
        "path": "",
        "default": "",
        "log_output": True,
        "agreed_to_decrypt": False,
        "launch_mode": LaunchMode.SYMLINK.value,
        "hook_fallback": True,
        "tags": {},
    }

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "ConfigService":  # noqa: ANN401
        """实现单例模式."""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance.__initialized = False
        return cls._instance

    def __init__(self, _storage: Optional["ConfigStorage"] = None) -> None:
        """初始化配置服务."""
        if self.__initialized:
            return

        self._runtime = RuntimeState()
        self._storage = _storage or ConfigStorage(
            config_path=ConfigData.path(), default_config=self._DEFAULT_CONFIG, error_handler=self._error_handler
        )

        self._config = self._storage.load()
        self.__initialized = True

    def __enter__(self) -> "ConfigService":
        """开启批量配置更新事务."""
        # noinspection PyProtectedMember
        self._storage._batch = True
        self._snapshot = deepcopy(self._config)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """结束批量配置更新事务并保存变更."""
        # noinspection PyProtectedMember
        self._storage._batch = False
        if exc_type is not None:
            self._config = self._snapshot
            # noinspection PyProtectedMember
            self._storage._config_changed = False
        else:
            # noinspection PyProtectedMember
            if self._storage._config_changed:
                self._storage.save(self._config)

    _log_handler: Optional[Callable[[str], None]] = None

    @classmethod
    def get_instance(cls) -> "ConfigService":
        """获取配置服务单例."""
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """重置配置服务单例."""
        if cls._instance is not None:
            cls._instance.shutdown()
        cls._instance = None
        cls._log_handler = None

    @classmethod
    def set_log_handler(cls, handler: Optional[Callable[[str], None]]) -> None:
        """设置错误日志处理器."""
        cls._log_handler = handler

    def _error_handler(self, message: str) -> None:
        """分发配置存储错误信息."""
        if self._log_handler:
            try:
                self._log_handler(message)
            except (RuntimeError, TypeError):
                pass

    def shutdown(self) -> None:
        """保存配置到磁盘."""
        # noinspection PyProtectedMember
        if self._storage._config_changed:
            self._storage.save(self._config)

    def _get_field(self, name: str, expected_type: Type[T], default_value: T) -> T:
        """读取并转换配置字段值."""
        value = self._config.get(name)
        if value is None:
            return default_value
        if not isinstance(value, expected_type):
            try:
                value = expected_type(value)
            except (ValueError, TypeError):
                value = default_value
        return value

    def _set_field(self, name: str, expected_type: Type[T], value: Any) -> None:  # noqa: ANN401
        """修改配置字段值并保存."""
        if value is not None and not isinstance(value, expected_type):
            raise TypeError(f"字段 '{name}' 类型错误：期望 {expected_type.__name__}, 实际为 {type(value).__name__}")

        self._config[name] = value
        # noinspection PyProtectedMember
        self._storage._config_changed = True
        # noinspection PyProtectedMember
        if not self._storage._batch:
            self._storage.save(self._config)

    @property
    def client(self) -> str:
        """获取客户端可执行文件名."""
        return self._get_field("client", str, TELEGRAM_EXE)

    @client.setter
    def client(self, value: str) -> None:
        """设置客户端可执行文件名."""
        self._set_field("client", str, value)

    @property
    def path(self) -> str:
        """获取客户端数据目录路径."""
        return self._get_field("path", str, "")

    @path.setter
    def path(self, value: str) -> None:
        """设置客户端数据目录路径."""
        self._set_field("path", str, value)

    @property
    def default(self) -> str:
        """获取默认账户标签."""
        return self._get_field("default", str, "")

    @default.setter
    def default(self, value: str) -> None:
        """设置默认账户标签."""
        self._set_field("default", str, value)

    @property
    def tags(self) -> Dict[str, Dict[str, Any]]:
        """获取已注册账户列表."""
        return self._get_field("tags", dict, {})

    @tags.setter
    def tags(self, value: Dict[str, Dict[str, Any]]) -> None:
        """设置已注册账户列表."""
        self._set_field("tags", dict, value)

    @property
    def log_output(self) -> bool:
        """获取日志输出状态."""
        return self._get_field("log_output", bool, True)

    @log_output.setter
    def log_output(self, value: bool) -> None:
        """设置日志输出状态."""
        self._set_field("log_output", bool, value)

    @property
    def agreed_to_decrypt(self) -> bool:
        """获取密钥解密同意状态."""
        return self._get_field("agreed_to_decrypt", bool, False)

    @agreed_to_decrypt.setter
    def agreed_to_decrypt(self, value: bool) -> None:
        """设置密钥解密同意状态."""
        self._set_field("agreed_to_decrypt", bool, value)

    @property
    def launch_mode(self) -> LaunchMode:
        """获取启动模式."""
        value = self._get_field("launch_mode", str, LaunchMode.SYMLINK.value)
        try:
            return LaunchMode(value)
        except ValueError:
            return LaunchMode.SYMLINK

    @launch_mode.setter
    def launch_mode(self, value: "LaunchMode | str") -> None:
        """设置启动模式."""
        if isinstance(value, LaunchMode):
            value = value.value
        self._set_field("launch_mode", str, value)

    @property
    def hook_fallback(self) -> bool:
        """获取 hook 失败降级状态."""
        return self._get_field("hook_fallback", bool, True)

    @hook_fallback.setter
    def hook_fallback(self, value: bool) -> None:
        """设置 hook 失败降级状态."""
        self._set_field("hook_fallback", bool, value)

    @property
    def start_time(self) -> Optional[datetime]:
        """获取会话启动时间."""
        return self._runtime.start_time

    @start_time.setter
    def start_time(self, v: datetime | None) -> None:
        """设置会话启动时间."""
        self._runtime.start_time = v

    @property
    def config_check(self) -> bool:
        """获取配置检查状态."""
        return self._runtime.config_check

    @config_check.setter
    def config_check(self, v: bool) -> None:
        """设置配置检查状态."""
        self._runtime.config_check = v

    @property
    def tag(self) -> str:
        """获取账户标签."""
        return self._runtime.tag

    @tag.setter
    def tag(self, v: str) -> None:
        """设置账户标签."""
        self._runtime.tag = str(v) if v is not None else ""

    @property
    def force_key_login(self) -> bool:
        """获取强制密钥登录状态."""
        return self._runtime.force_key_login

    @force_key_login.setter
    def force_key_login(self, v: bool) -> None:
        """设置强制密钥登录状态."""
        self._runtime.force_key_login = bool(v)

    @property
    def pwd(self) -> str:
        """获取临时解密密码."""
        return self._runtime.password

    @pwd.setter
    def pwd(self, v: str) -> None:
        """设置临时解密密码."""
        self._runtime.password = str(v) if v is not None else ""

    @property
    def decrypted(self) -> bool:
        """获取解密成功状态."""
        return self._runtime.decrypted

    @decrypted.setter
    def decrypted(self, v: bool) -> None:
        """设置解密成功状态."""
        self._runtime.decrypted = bool(v)

    @property
    def has_backup(self) -> bool:
        """检查是否存在密钥备份."""
        return self.has_complete_keys(self.tag)

    @property
    def configs(self) -> Dict[str, Any]:
        """获取全局配置字典副本."""
        return self._config.copy()

    @property
    def config_file(self) -> Path:
        """获取配置文件路径."""
        # noinspection PyProtectedMember
        return self._storage._config_path

    def get_all_accounts(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已注册账户的数据."""
        return dict(self.tags)

    def get_tag_list(self) -> list[str]:
        """获取所有账户的标签列表."""
        return list(self.tags.keys())

    def get_account(self, tag: str) -> Dict[str, Any]:
        """获取指定账户的详细数据."""
        return self.tags.get(tag, {"id": "", "folder": "", "info": "", "identity": "", "key": ""})

    def set_account(self, tag: str, data: Dict[str, Any]) -> None:
        """设置或更新指定账户的数据."""
        tags: Dict[str, Dict[str, Any]] = dict(self.tags)
        tags[tag] = data
        self.tags = tags

    def remove_account(self, tag: str) -> None:
        """移除指定账户的注册信息."""
        tags: Dict[str, Dict[str, Any]] = self.tags.copy()
        if tag in tags:
            del tags[tag]
            self.tags = tags

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """批量更新配置项."""
        with self:
            for key, value in updates.items():
                setattr(self, key, value)

    def login_with_keys(self, tag: str, tdata_path: str) -> bool:
        """使用备份的密钥还原登录状态."""
        return TelegramKeyManager.login_with_keys(tag, tdata_path, self)

    def backup_account_keys(self, tag: str, folder_path: Path) -> bool:
        """备份指定账户的密钥文件."""
        return TelegramKeyManager.backup_keys(tag, folder_path, self)

    def has_complete_keys(self, tag: str) -> bool:
        """检查指定账户是否有完整的备份密钥."""
        acc = self.get_account(tag)
        return all(acc.get(k) for k in ("key", "identity", "info"))

    def sync_all_account_paths(self) -> None:
        """同步更新账户的物理路径."""
        if not self.path or not os.path.isdir(self.path):
            return

        try:
            base_dir = Path(self.path)
            tag_to_folder = {}
            for entry in base_dir.iterdir():
                if entry.is_symlink():
                    continue
                if entry.is_dir():
                    tas_tag_file = entry / "tas_tag"
                    if tas_tag_file.is_file():
                        try:
                            tag_name = tas_tag_file.read_text(encoding="utf-8").strip()
                            tag_to_folder[tag_name] = entry.name
                        except (OSError, UnicodeDecodeError) as e:
                            self._error_handler(f"读取或解析目录 {entry.name} 中的 tas_tag 失败: {e}")

            updated_tags: Dict[str, Dict[str, Any]] = self.tags.copy()
            changed = False
            for tag, info in updated_tags.items():
                real_folder = tag_to_folder.get(tag)
                if real_folder and info.get("folder") != real_folder:
                    info["folder"] = real_folder
                    changed = True
            if changed:
                self.tags = updated_tags
        except OSError as e:
            self._error_handler(f"遍历账户目录失败: {e}")

    def watch_time(self) -> str:
        """获取活跃账户的格式化运行时间."""
        start_time = self.start_time
        if start_time is None:
            return "0时0分0秒"
        return format_timedelta(datetime.now() - start_time)
