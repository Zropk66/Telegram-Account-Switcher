"""
事件总线 — 线程安全的发布/订阅实现。

模块间通过事件通信，不再依赖回调列表或轮询共享状态。
"""
from __future__ import annotations

import traceback
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Callable, Generic, Optional, TypeVar

from src.core.logger import Logger

T = TypeVar("T")

# 事件类型常量
PROCESS_STATUS_CHANGED = "process.status_changed"
ACCOUNT_LOGIN_DETECTED = "account.login_detected"
ACCOUNT_RESTORE_COMPLETED = "account.restore_completed"
KEY_BACKUP_COMPLETED = "key.backup_completed"
APP_COMPLETION = "app.completion"
APP_SHUTDOWN = "app.shutdown"

# 全局单例相关
_event_bus_ctx: ContextVar[Optional["EventBus"]] = ContextVar("event_bus", default=None)
_event_bus_lock = Lock()
_event_bus_instance: Optional["EventBus"] = None


@dataclass(frozen=True)
class Event(Generic[T]):
    """不可变的事件载体。"""

    type: str
    payload: T
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProcessStatusChanged:
    """Telegram 进程存活状态发生变化。"""

    is_alive: bool
    pid: Optional[int] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class AccountLoginDetected:
    """检测到账户登录成功。"""

    tag: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class AccountRestoreCompleted:
    """默认账户恢复完成。"""

    success: bool
    tag: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class KeyBackupCompleted:
    """密钥备份完成。"""

    tag: str
    success: bool
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class AppCompletionEvent:
    """应用主任务结束。"""

    success: bool
    message: str = ""
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class AppShutdownEvent:
    """应用即将关闭。"""

    reason: str = "normal"
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class EventBus:
    """
    线程安全的事件总线。

    - Lock 保护订阅表，支持多线程并发发布/订阅
    - 单个 handler 抛异常不会影响其余 handler
    - 开启 debug 模式可打印所有发布/订阅日志
    """

    def __init__(self, logger: Optional[Logger] = None):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = Lock()
        self._debug = False
        self._logger = logger

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """注册事件监听器。"""
        with self._lock:
            self._subscribers[event_type].append(handler)
        if self._debug:
            print(f"[EventBus] 订阅: {event_type} <- {handler.__name__}")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """移除事件监听器。"""
        with self._lock:
            handlers = self._subscribers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def publish(self, event: Event) -> None:
        """同步派发事件到所有订阅者。"""
        with self._lock:
            handlers = list(self._subscribers.get(event.type, []))
        if self._debug:
            print(f"[EventBus] 发布: {event.type} -> {len(handlers)} 个订阅者")
        for handler in handlers:
            try:
                handler(event.payload)
            except Exception as e:
                error_msg = f"[EventBus] handler {handler.__name__} 执行失败: {e}"
                if self._logger:
                    self._logger.exception(error_msg, exc=e)
                else:
                    print(error_msg)
                    traceback.print_exc()

    def clear(self) -> None:
        """清空所有订阅（主要用于测试）。"""
        with self._lock:
            self._subscribers.clear()


def get_event_bus() -> EventBus:
    """
    获取 EventBus 实例。

    优先返回 ContextVar 中的实例（测试用），否则返回全局单例。
    """
    ctx_bus = _event_bus_ctx.get()
    if ctx_bus is not None:
        return ctx_bus

    global _event_bus_instance
    if _event_bus_instance is None:
        with _event_bus_lock:
            if _event_bus_instance is None:
                _event_bus_instance = EventBus()
    assert _event_bus_instance is not None
    return _event_bus_instance


def set_event_bus(bus: Optional[EventBus]) -> None:
    """设置当前上下文的 EventBus 实例，传入 None 则清除。"""
    _event_bus_ctx.set(bus)
