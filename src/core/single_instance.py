"""单实例防护锁。"""
import ctypes
import threading
from ctypes import wintypes
from typing import Optional

from src.core.constants import SINGLE_INSTANCE_LOCK_NAME, MUTEX_PREFIX
from src.core.exceptions import SingleInstanceException

_kernel32 = ctypes.windll.kernel32


class SingleInstanceLock:
    """单实例锁。"""

    _instance: Optional['SingleInstanceLock'] = None
    _lock = threading.Lock()

    def __init__(self, lock_name: str = SINGLE_INSTANCE_LOCK_NAME):
        """初始化锁。"""
        self._lock_name = lock_name
        self._mutex_name = f"{MUTEX_PREFIX}{lock_name}"
        self._handle: Optional[int] = None
        self._acquired = False
        self._init_windows()

    def _init_windows(self) -> None:
        """创建跨会话可见的 Windows Mutex。"""
        self._handle = _kernel32.CreateMutexW(
            None,
            wintypes.BOOL(False),
            self._mutex_name
        )
        if not self._handle:
            raise SingleInstanceException(f"创建互斥体失败，错误码: {ctypes.get_last_error()}")

    def acquire(self, timeout: float = 0) -> bool:
        """尝试获取锁。"""
        if self._acquired:
            return True

        WAIT_TIMEOUT = 0x00000102
        WAIT_OBJECT_0 = 0
        timeout_ms = int(timeout * 1000) if timeout > 0 else 0

        result = _kernel32.WaitForSingleObject(
            self._handle,
            wintypes.DWORD(timeout_ms)
        )

        if result == WAIT_OBJECT_0:
            self._acquired = True
            return True
        elif result == WAIT_TIMEOUT:
            return False
        else:
            raise SingleInstanceException(
                f"等待互斥体失败，错误码: {ctypes.get_last_error()}"
            )

    def release(self) -> None:
        """释放互斥锁。"""
        if self._acquired:
            _kernel32.ReleaseMutex(self._handle)
            self._acquired = False

    def close(self) -> None:
        """关闭系统句柄。"""
        self.release()
        if self._handle:
            _kernel32.CloseHandle(self._handle)
            self._handle = None

    @classmethod
    def ensure_single_instance(cls, lock_name: str = SINGLE_INSTANCE_LOCK_NAME) -> 'SingleInstanceLock':
        """获取全局单实例锁。"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(lock_name)

        if not cls._instance.acquire(timeout=0):
            raise SingleInstanceException(
                "TAS 已在运行中，请勿重复启动。\n\n"
                "如果确认没有其他实例，请手动清理锁文件后重试。"
            )

        return cls._instance

    @classmethod
    def cleanup(cls) -> None:
        """清理类级别的单实例锁。"""
        if cls._instance is not None:
            cls._instance.close()
            cls._instance = None

    def __enter__(self):
        """进入上下文管理器。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器。"""
        self.close()

    def __del__(self):
        """析构对象并释放句柄。"""
        self.close()
