"""
日志模块测试。

验证 Logger 的测试隔离入口能恢复全局注入状态，避免单例和回调泄漏到后续用例。
"""

from src.core.logger import (
    DefaultConfigProvider,
    Logger,
    _popup_state,
    reset_logger_state,
    set_config_provider,
    set_popup_handler,
)


class DummyConfigProvider:
    def get(self, key, default=None):
        return True


def test_reset_logger_state_restores_injected_globals():
    """重置日志状态时应清空 UI 回调并恢复默认配置提供者。"""
    set_popup_handler(lambda *_: None)
    set_config_provider(DummyConfigProvider())
    Logger.get_instance()

    reset_logger_state()

    assert _popup_state["handler"] is None

    from src.core.logger import _config_provider
    assert isinstance(_config_provider, DefaultConfigProvider)


def test_logger_reset_instance_creates_new_singleton():
    """Logger 单例重置后应在下一次访问时重新初始化。"""
    first = Logger.get_instance()

    Logger.reset_instance()
    second = Logger.get_instance()

    assert second is not first
