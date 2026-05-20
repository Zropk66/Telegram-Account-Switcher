"""
核心功能层的公共导出入口。

集中暴露账户切换、配置、日志、进程、文件系统和接口类型，方便上层模块按能力导入。
"""
from .account import (
    AccountSwitcher,
    recovery
)
from .crypto import AESCipher
from .exceptions import (
    TASException,
    TASConfigException,
)
from .event_bus import (
    EventBus,
    get_event_bus,
    Event,
    ProcessStatusChanged,
    AccountLoginDetected,
    AccountRestoreCompleted,
    KeyBackupCompleted,
    AppCompletionEvent,
    AppShutdownEvent,
    PROCESS_STATUS_CHANGED,
    ACCOUNT_LOGIN_DETECTED,
    ACCOUNT_RESTORE_COMPLETED,
    KEY_BACKUP_COMPLETED,
    APP_COMPLETION,
    APP_SHUTDOWN,
)
from .interfaces import (
    ILogger,
    IConfigProvider,
    IProcessService,
    IProcessManager,
    ICipherService,
    IEventBus,
    IAccountRecoveryService,
    ProcessInfo,
)
from .logger import Logger
from .process_manager import (
    ProcessManager,
    ProcessMonitor
)
from .process_service import (
    PsutilProcessService,
    MockProcessService,
)
from .single_instance import (
    SingleInstanceLock,
    SingleInstanceException,
)

__all__ = [
    'ProcessManager', 'ProcessMonitor',
    'TASException', 'TASConfigException', 'SingleInstanceException',
    'AccountSwitcher', 'Logger',
    'AESCipher', 'recovery',
    'SingleInstanceLock',
    'ILogger', 'IConfigProvider', 'IProcessService', 'IProcessManager',
    'ICipherService', 'IEventBus',
    'IAccountRecoveryService', 'ProcessInfo',
    'PsutilProcessService', 'MockProcessService',
    'EventBus', 'get_event_bus', 'Event',
    'ProcessStatusChanged', 'AccountLoginDetected', 'AccountRestoreCompleted',
    'KeyBackupCompleted', 'AppCompletionEvent', 'AppShutdownEvent',
    'PROCESS_STATUS_CHANGED', 'ACCOUNT_LOGIN_DETECTED', 'ACCOUNT_RESTORE_COMPLETED',
    'KEY_BACKUP_COMPLETED', 'APP_COMPLETION', 'APP_SHUTDOWN',
]
