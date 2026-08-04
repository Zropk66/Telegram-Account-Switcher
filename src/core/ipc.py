"""进程间通信 (IPC) 模块，支持主从 TAS 实例控制权移交."""

import threading
import traceback
from multiprocessing.connection import Client, Listener
from typing import Callable, Optional

from src.core.constants import IPC_AUTH_KEY, IPC_PIPE_ADDRESS
from src.core.logger import Logger


class IPCServer:
    """IPC 服务端."""

    def __init__(self, handler: Callable[[str], None], logger: Optional[Logger] = None) -> None:
        """初始化 IPC 服务端."""
        self.handler = handler
        self.logger = logger or Logger()
        self._listener: Optional[Listener] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """启动 IPC 监听线程."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True, name="IPC-Server-Thread")
        self._thread.start()

    def stop(self) -> None:
        """停止 IPC 监听服务."""
        self._running = False
        if self._listener:
            try:
                self._listener.close()
            except Exception:
                traceback.print_exc()

    def _listen(self) -> None:
        """后台监听通道循环."""
        try:
            self._listener = Listener(IPC_PIPE_ADDRESS, authkey=IPC_AUTH_KEY)
        except Exception as e:
            self.logger.debug(f"IPC Listener 创建失败: {e}")
            return

        while self._running:
            try:
                conn = self._listener.accept()
                msg = conn.recv()
                conn.close()
                if isinstance(msg, str) and msg:
                    self.logger.debug(f"收到从实例 IPC 指令: {msg}")
                    self.handler(msg)
            except Exception as e:
                if not self._running:
                    break
                self.logger.debug(f"IPC 接收异常: {e}")


class IPCClient:
    """IPC 客户端."""

    @staticmethod
    def send_command(command: str) -> bool:
        """向主 TAS 进程发送指令，成功返回 True."""
        try:
            conn = Client(IPC_PIPE_ADDRESS, authkey=IPC_AUTH_KEY)
            conn.send(command)
            conn.close()
            return True
        except Exception:
            return False
