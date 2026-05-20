# -*- coding: utf-8 -*-
# @File    : events.py
# @Time    : 2026/5/14 14:37
# @Author  : Zropk
"""
events.py 模块。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Event(Generic[T]):
    """不可变的事件对象，包裹具体的业务数据。"""
    type: str
    payload: T
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProcessStatusChanged:
    """Telegram 进程状态变更数据。"""
    is_alive: bool
    pid: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AccountLoginDetected:
    """成功登录特定账户的数据。"""
    tag: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AccountRestoreCompleted:
    """默认账户现场还原结果数据。"""
    success: bool
    tag: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class KeyBackupCompleted:
    """密钥文件备份结果数据。"""
    tag: str
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AppCompletionEvent:
    """应用生命周期结束或主任务完成数据。"""
    success: bool
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AppShutdownEvent:
    """应用即将退出信号数据。"""
    reason: str = "normal"
    timestamp: datetime = field(default_factory=datetime.now)
