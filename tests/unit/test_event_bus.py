"""
EventBus 事件总线单元测试。

验证事件订阅、发布、取消订阅、异常隔离和上下文切换的行为。
"""
import pytest
from unittest.mock import MagicMock, call

from src.core.event_bus import EventBus, Event, get_event_bus, set_event_bus


class TestEventBus:
    """覆盖应用内事件总线的可靠性约束。"""

    def test_subscribe_and_publish(self):
        """验证同一事件的多个订阅者都能收到正确 payload。"""
        bus = EventBus()
        test_event_type = "test.event"
        test_payload = {"data": "test_value"}

        handler1 = MagicMock()
        handler2 = MagicMock()

        bus.subscribe(test_event_type, handler1)
        bus.subscribe(test_event_type, handler2)

        event = Event(type=test_event_type, payload=test_payload)
        bus.publish(event)

        handler1.assert_called_once_with(test_payload)
        handler2.assert_called_once_with(test_payload)

    def test_handler_exception_isolation(self, mock_logger):
        """验证单个事件处理器失败不会阻断其他订阅者。"""
        bus = EventBus(logger=mock_logger)
        test_event_type = "test.event"
        test_payload = {"data": "test_value"}

        handler_normal = MagicMock()

        def handler_error(payload):
            raise Exception("测试异常")

        handler3 = MagicMock()

        bus.subscribe(test_event_type, handler_normal)
        bus.subscribe(test_event_type, handler_error)
        bus.subscribe(test_event_type, handler3)

        event = Event(type=test_event_type, payload=test_payload)
        bus.publish(event)

        handler_normal.assert_called_once_with(test_payload)
        handler3.assert_called_once_with(test_payload)
        mock_logger.exception.assert_called_once()

    def test_unsubscribe_removes_handler(self):
        """验证取消订阅后，处理器不会再收到后续事件。"""
        bus = EventBus()
        test_event_type = "test.event"
        test_payload = {"data": "test_value"}

        handler1 = MagicMock()
        handler2 = MagicMock()

        bus.subscribe(test_event_type, handler1)
        bus.subscribe(test_event_type, handler2)

        bus.unsubscribe(test_event_type, handler1)

        event = Event(type=test_event_type, payload=test_payload)
        bus.publish(event)

        handler1.assert_not_called()
        handler2.assert_called_once_with(test_payload)

    def test_unsubscribe_non_existent_handler_does_not_crash(self):
        """验证取消不存在的订阅时保持幂等，不影响调用方。"""
        bus = EventBus()
        test_event_type = "test.event"
        handler = MagicMock()

        bus.unsubscribe(test_event_type, handler)

    def test_publish_no_subscribers_does_not_crash(self):
        """验证没有订阅者的事件可以安全发布。"""
        bus = EventBus()
        event = Event(type="test.event", payload={"data": "test"})

        bus.publish(event)

    def test_context_isolation(self):
        """验证上下文切换后的事件总线实例互不污染。"""
        bus1 = EventBus()
        bus2 = EventBus()

        test_event_type = "test.event"
        payload1 = {"data": "bus1"}
        payload2 = {"data": "bus2"}

        handler1 = MagicMock()
        handler2 = MagicMock()

        set_event_bus(bus1)
        bus1.subscribe(test_event_type, handler1)

        current_bus1 = get_event_bus()
        current_bus1.publish(Event(type=test_event_type, payload=payload1))

        set_event_bus(bus2)
        bus2.subscribe(test_event_type, handler2)

        current_bus2 = get_event_bus()
        current_bus2.publish(Event(type=test_event_type, payload=payload2))

        handler1.assert_called_once_with(payload1)
        handler2.assert_called_once_with(payload2)

        assert current_bus1 is bus1
        assert current_bus2 is bus2
        assert bus1 is not bus2

        set_event_bus(None)

    def test_clear_removes_all_subscribers(self):
        """验证 clear 会移除所有订阅者。"""
        bus = EventBus()
        test_event_type = "test.event"

        handler1 = MagicMock()
        handler2 = MagicMock()

        bus.subscribe(test_event_type, handler1)
        bus.subscribe(test_event_type, handler2)

        bus.clear()
        bus.publish(Event(type=test_event_type, payload={"data": "test"}))

        handler1.assert_not_called()
        handler2.assert_not_called()
