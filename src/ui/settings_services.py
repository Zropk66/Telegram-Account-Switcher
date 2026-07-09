"""设置界面的后台服务."""

from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from src.core import TASException


class SignalsEmitter(QObject):
    """任务结果通信器."""

    finished = Signal(object)
    warning = Signal(object)
    error = Signal(object)
    exception = Signal(Exception)


class TaskRunner(QRunnable):
    """基于 `QThreadPool` 的任务执行运行器."""

    def __init__(self, func: Callable) -> None:
        """在后台执行的无参可调用对象."""
        super().__init__()
        self.func = func
        self.signals = SignalsEmitter()

    @Slot()
    def run(self) -> None:
        """执行任务逻辑，并根据结果发射对应信号."""
        try:
            result = self.func()
            self.signals.finished.emit(result)
        except TASException as e:
            self.signals.error.emit(e)
        except Exception as e:
            self.signals.exception.emit(e)
