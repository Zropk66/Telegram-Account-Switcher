"""
TaskRunner 异步任务运行器单元测试。

验证任务执行结果能映射到正确的 Qt 信号，确保 UI 层可以区分成功、业务异常和未知异常。
"""
import os
import pytest
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from src.ui.settings_services import TaskRunner
from src.core import TASException

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="module")
def qapp():
    """初始化 Qt 应用上下文，保证信号系统可用。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


def test_run_emits_finished_on_success(qapp):
    """验证任务成功时发射 finished 信号并传递返回值。"""
    test_result = "success result"
    captured = []

    def success_func():
        return test_result

    runner = TaskRunner(success_func)
    runner.signals.finished.connect(captured.append)

    runner.run()

    assert len(captured) == 1
    assert captured[0] == test_result


def test_run_emits_error_on_tas_exception(qapp):
    """验证业务异常会进入 error 信号通道。"""
    test_error = TASException("test TAS exception")
    captured_errors = []

    def tas_error_func():
        raise test_error

    runner = TaskRunner(tas_error_func)
    runner.signals.error.connect(captured_errors.append)

    runner.run()

    assert len(captured_errors) == 1
    assert captured_errors[0] == test_error


def test_run_emits_exception_on_generic_error(qapp):
    """验证未知异常会进入 exception 信号通道，避免被误判为业务错误。"""
    test_exception = ValueError("test generic exception")
    captured_exceptions = []

    def generic_error_func():
        raise test_exception

    runner = TaskRunner(generic_error_func)
    runner.signals.exception.connect(captured_exceptions.append)

    runner.run()

    assert len(captured_exceptions) == 1
    assert isinstance(captured_exceptions[0], ValueError)
    assert str(captured_exceptions[0]) == str(test_exception)
