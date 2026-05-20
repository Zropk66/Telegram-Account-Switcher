"""
设置界面的后台异步服务模块。

提供基于 `QRunnable` 和信号机制的异步任务执行框架，用于在后台线程处理
文件扫描、配置加载等耗时操作，避免阻塞 UI 线程。
"""

from PySide6.QtCore import QObject, Signal, QRunnable, Slot

from src.core import TASException


class SignalsEmitter(QObject):
    """异步任务结果通信器。"""

    finished = Signal(object)
    warning = Signal(object)
    error = Signal(object)
    exception = Signal(Exception)


class TaskRunner(QRunnable):
    """基于 `QThreadPool` 的任务执行运行器。"""

    def __init__(self, func):
        """在后台执行的无参可调用对象"""
        super().__init__()
        self.func = func
        self.signals = SignalsEmitter()

    @Slot()
    def run(self):
        """执行任务逻辑，并根据结果发射对应信号。"""
        try:
            result = self.func()
            self.signals.finished.emit(result)
        except TASException as e:
            self.signals.error.emit(e)
        except Exception as e:
            self.signals.exception.emit(e)
