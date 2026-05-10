from PySide6.QtCore import QObject, Signal, QRunnable, Slot

from src.core import TASException


class SignalsEmitter(QObject):
    """通用的信号集合，TaskRunner 通过它把结果或异常传回主线程。"""

    finished = Signal(object)
    warning = Signal(object)
    error = Signal(object)
    exception = Signal(Exception)
    signal = Signal(object)


class TaskRunner(QRunnable):
    """在 QThreadPool 中执行一个函数，结果通过信号发回 UI 线程。"""

    def __init__(self, func):
        super().__init__()
        self.func = func
        self.signals = SignalsEmitter()

    @Slot()
    def run(self):
        try:
            result = self.func()
            self.signals.finished.emit(result)
        except TASException as e:
            self.signals.error.emit(e)
        except Exception as e:
            self.signals.exception.emit(e)
