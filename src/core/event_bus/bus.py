# -*- coding: utf-8 -*-
# @File    : bus.py
# @Time    : 2026/5/14 14:36
# @Author  : Zropk
"""
bus.py 模块。
"""

from __future__ import annotations

import traceback
from collections import defaultdict
from contextvars import ContextVar
from threading import Lock
from typing import Callable, Optional, TYPE_CHECKING

from src.core.interfaces import IEventBus, ILogger

if TYPE_CHECKING:
    from core.event_bus.events import Event

_event_bus_ctx: ContextVar[Optional["EventBus"]] = ContextVar("event_bus", default=None)
_event_bus_lock = Lock()
_event_bus_instance: Optional["EventBus"] = None


class EventBus(IEventBus):
    """进程内的消息中转站。"""

    def __init__(self, logger: Optional[ILogger] = None):
        """初始化。"""
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = Lock()
        self._logger = logger

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """注册监听器。"""
        with self._lock:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """移除监听器。"""
        with self._lock:
            handlers = self._subscribers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def publish(self, event: "Event") -> None:
        """同步派发事件。"""
        with self._lock:
            handlers = list(self._subscribers.get(event.type, []))

        for handler in handlers:
            try:
                handler(event.payload)
            except Exception as e:
                if self._logger:
                    self._logger.exception(f"EventBus: 处理器 '{handler.__name__}' 执行失败", exc=e)
                else:
                    traceback.print_exc()

    def clear(self) -> None:
        """清空所有订阅（主要用于单元测试）。"""
        with self._lock:
            self._subscribers.clear()


def get_event_bus() -> EventBus:
    """获取全局或上下文相关的事件总线实例。"""
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
    """在当前上下文中注入新的事件总线。"""
    _event_bus_ctx.set(bus)
