# -*- coding: utf-8 -*-
# @File    : __init__.py
# @Time    : 2026/5/14 14:36
# @Author  : Zropk

from src.core.event_bus.events import (
    Event,
    ProcessStatusChanged,
    AccountLoginDetected,
    AccountRestoreCompleted,
    KeyBackupCompleted,
    AppCompletionEvent,
    AppShutdownEvent,
)
from src.core.event_bus.bus import EventBus, get_event_bus, set_event_bus
from src.core.event_bus.constants import (
    PROCESS_STATUS_CHANGED,
    ACCOUNT_LOGIN_DETECTED,
    ACCOUNT_RESTORE_COMPLETED,
    KEY_BACKUP_COMPLETED,
    APP_COMPLETION,
    APP_SHUTDOWN,
)

__all__ = [
    "EventBus",
    "Event",
    "ProcessStatusChanged",
    "AccountLoginDetected",
    "AccountRestoreCompleted",
    "KeyBackupCompleted",
    "AppCompletionEvent",
    "AppShutdownEvent",
    "get_event_bus",
    "set_event_bus",
    "PROCESS_STATUS_CHANGED",
    "ACCOUNT_LOGIN_DETECTED",
    "ACCOUNT_RESTORE_COMPLETED",
    "KEY_BACKUP_COMPLETED",
    "APP_COMPLETION",
    "APP_SHUTDOWN",
]
