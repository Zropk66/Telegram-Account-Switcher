"""
跨进程单实例防护。

使用 Windows Named Mutex 阻止 TAS 同时运行多个实例。
"""
import ctypes
from ctypes import wintypes
from typing import Optional

from src.core.exceptions import SingleInstanceException

_kernel32 = ctypes.windll.kernel32


class SingleInstanceLock:
    """基于 Global Windows Mutex 的单实例锁。"""

    _instance: Optional['SingleInstanceLock'] = None

    def __init__(self, lock_name: str = "TelegramAccountSwitcher"):
        """初始化。"""
        self._lock_name = lock_name
        self._mutex_name = f"Global\\{lock_name}"
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
        """尝试获取锁，已被其他实例持有时返回 False。"""
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
        """释放已持有的 Mutex。"""
        if self._acquired:
            _kernel32.ReleaseMutex(self._handle)
            self._acquired = False

    def close(self) -> None:
        """释放锁并关闭系统句柄。"""
        self.release()
        if self._handle:
            _kernel32.CloseHandle(self._handle)
            self._handle = None

    @classmethod
    def ensure_single_instance(cls, lock_name: str = "TelegramAccountSwitcher") -> 'SingleInstanceLock':
        """获取全局单实例锁，失败说明已有 TAS 实例正在运行。"""
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
        """内部方法：__enter__。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """内部方法：__exit__。"""
        self.close()

    def __del__(self):
        """内部方法：__del__。"""
        self.close()
