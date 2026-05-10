# -*- coding: utf-8 -*-
from PySide6.QtCore import QObject, Signal, QRunnable, Slot

from src.modules import TASException


class SignalsEmitter(QObject):
    """通用的信号发射器"""
    finished = Signal(object)
    warning = Signal(object)
    error = Signal(object)
    exception = Signal(Exception)
    signal = Signal(object)


class TaskRunner(QRunnable):
    """异步任务执行器"""

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
