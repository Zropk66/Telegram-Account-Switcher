"""
核心抽象接口定义。

使用 Protocol (结构化子类型) 定义系统各组件的契约。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, Union, runtime_checkable


@runtime_checkable
class ILogger(Protocol):
    """通用日志接口。"""

    def debug(self, message: str, popup: bool = False, **kwargs) -> None: ...

    def info(self, message: str, popup: bool = False, **kwargs) -> None: ...

    def warning(self, message: str, popup: bool = False, **kwargs) -> None: ...

    def error(self, message: str, popup: bool = False, **kwargs) -> None: ...

    def critical(self, message: str, popup: bool = False, **kwargs) -> None: ...

    def exception(self, message: str, exc: Exception, popup: bool = False, **kwargs) -> None: ...


@runtime_checkable
class IConfigProvider(Protocol):
    """配置管理契约。"""

    @property
    def client(self) -> str: ...

    @client.setter
    def client(self, value: str) -> None: ...

    @property
    def path(self) -> str: ...

    @path.setter
    def path(self, value: str) -> None: ...

    @property
    def default(self) -> str: ...

    @default.setter
    def default(self, value: str) -> None: ...

    @property
    def tags(self) -> Dict[str, Dict[str, Any]]: ...

    @tags.setter
    def tags(self, value: Dict[str, Dict[str, Any]]) -> None: ...

    @property
    def log_output(self) -> bool: ...

    @log_output.setter
    def log_output(self, value: bool) -> None: ...

    @property
    def agreed_to_decrypt(self) -> bool: ...

    @agreed_to_decrypt.setter
    def agreed_to_decrypt(self, value: bool) -> None: ...

    @property
    def tag(self) -> str: ...

    @tag.setter
    def tag(self, value: str) -> None: ...

    @property
    def pwd(self) -> str: ...

    @pwd.setter
    def pwd(self, value: str) -> None: ...

    @property
    def decrypted(self) -> bool: ...

    @decrypted.setter
    def decrypted(self, value: bool) -> None: ...

    @property
    def force_key_login(self) -> bool: ...

    @force_key_login.setter
    def force_key_login(self, value: bool) -> None: ...

    @property
    def start_time(self) -> Optional[datetime]: ...

    @start_time.setter
    def start_time(self, value: Optional[datetime]) -> None: ...

    @property
    def has_backup(self) -> bool: ...

    @property
    def configs(self) -> Dict[str, Any]: ...

    @property
    def config_file(self) -> Path: ...

    def get_account(self, tag: str) -> Dict[str, Any]: ...

    def set_account(self, tag: str, data: Dict[str, Any]) -> None: ...

    def get_all_accounts(self) -> Dict[str, Dict[str, Any]]: ...

    def has_complete_keys(self, tag: str) -> bool: ...

    def backup_account_keys(self, tag: str, folder_path: Path) -> bool: ...

    def login_with_keys(self, tag: str, tdata_path: str) -> bool: ...

    def sync_all_account_paths(self) -> None: ...

    def batch_update(self, updates: Dict[str, Any]) -> None: ...

    def watch_time(self) -> str: ...

    def shutdown(self) -> None: ...


@dataclass
class ProcessInfo:
    """跨平台的进程摘要信息。"""
    pid: int
    name: str


@runtime_checkable
class IProcessService(Protocol):
    """底层 OS 进程操作抽象。"""

    def find_processes(self, name: str) -> List[ProcessInfo]: ...

    def terminate(self, pid: int) -> bool: ...

    def kill(self, pid: int) -> bool: ...

    def wait_for_process(self, pid: int, timeout: float) -> bool: ...


@runtime_checkable
class IProcessManager(Protocol):
    """高层进程管理器契约。"""

    def start_process(self, wait: bool = True) -> bool: ...

    def kill_process(self, client: str) -> bool: ...

    def kill_and_guard(self, client_name: str, restart_on_exit: bool = False): ...


@runtime_checkable
class ICipherService(Protocol):
    """加解密核心契约。"""

    def encrypt(self, path: Union[str, Path], save: bool = True) -> bool: ...

    def decrypt(self, path: Union[str, Path], save: bool = True) -> bool: ...

    @staticmethod
    def is_encrypted(path_or_bytes: Union[str, Path, bytes]) -> bool: ...


@runtime_checkable
class IEventBus(Protocol):
    """事件分发契约，支持进程状态、登录状态等全局解耦通信。"""

    def subscribe(self, event_type: str, handler: Callable) -> None: ...

    def unsubscribe(self, event_type: str, handler: Callable) -> None: ...

    def publish(self, event: Any) -> None: ...

    def clear(self) -> None: ...


@runtime_checkable
class IAccountRecoveryService(Protocol):
    """异常恢复契约。"""

    def cleanup_orphan_folders(self, base_path_str: str) -> None: ...

    def recover_account(self, tag: str, config_manage: IConfigProvider) -> bool: ...


@runtime_checkable
class IAccountMonitor(Protocol):
    """后台监控契约。"""

    def run(self) -> None: ...


@runtime_checkable
class IEnvService(Protocol):
    """环境感知与同步契约。"""

    @staticmethod
    def search_client() -> Tuple[str, str]: ...

    @staticmethod
    def scan_accounts(base_path: str, passcode: Optional[str] = None) -> Dict[str, Dict[str, Any]]: ...


@runtime_checkable
class ICryptoService(Protocol):
    """Telegram 数据深度解密契约。"""

    @staticmethod
    def decrypt_accounts(tdata_path: Path, passcode: Optional[str] = None) -> List[Dict[str, Any]]: ...

    @staticmethod
    def decrypt_account_id(tdata_path: Path, passcode: Optional[str] = None) -> Optional[str]: ...


@runtime_checkable
class IKeyManager(Protocol):
    """免密密钥管理契约。"""

    @staticmethod
    def backup_keys(tag: str, folder_path: Path, config_service: IConfigProvider) -> bool: ...

    @staticmethod
    def login_with_keys(tag: str, tdata_path: str, config_service: IConfigProvider) -> bool: ...
