"""TAS 与 hook.dll 的 IPC 通信服务端."""

import ctypes
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable, Optional

from src.core.logger import Logger

_ipc_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_MESSAGE = 0x00000004
PIPE_READMODE_MESSAGE = 0x00000002
PIPE_WAIT = 0x00000000
PIPE_UNLIMITED_INSTANCES = 255
ERROR_PIPE_CONNECTED = 535

_INVALID_HANDLE_VALUE = (1 << (64 if ctypes.sizeof(ctypes.c_void_p) == 8 else 32)) - 1

_ipc_kernel32.CreateNamedPipeW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
]
_ipc_kernel32.CreateNamedPipeW.restype = wintypes.HANDLE

_ipc_kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
_ipc_kernel32.ConnectNamedPipe.restype = wintypes.BOOL

_ipc_kernel32.ReadFile.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
_ipc_kernel32.ReadFile.restype = wintypes.BOOL

_ipc_kernel32.WriteFile.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
_ipc_kernel32.WriteFile.restype = wintypes.BOOL

_ipc_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_ipc_kernel32.CloseHandle.restype = wintypes.BOOL

_ipc_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
_ipc_kernel32.CreateFileW.restype = wintypes.HANDLE


@dataclass
class HookClient:
    pid: int
    tdata_name: str
    handle: int
    is_listener: bool = False
    tag_name: Optional[str] = None


class HookIPCServer:
    """TAS 与 hook.dll 的 IPC 服务端."""

    PIPE_NAME = r"\\.\pipe\TAS_HOOK_IPC"
    BUFFER_SIZE = 4096

    def __init__(
        self,
        logger: Logger,
        url_handler: Callable[[str], None],
        exit_handler: Optional[Callable[[int], None]] = None,
        tag_resolver: Optional[Callable[[str], Optional[str]]] = None,
    ) -> None:
        self._logger = logger
        self._url_handler = url_handler
        self._exit_handler = exit_handler
        self._tag_resolver = tag_resolver
        self._clients: dict[int, HookClient] = {}
        self._listener_pid: Optional[int] = None
        self._last_confirmed_pid: Optional[int] = None
        self._lock = threading.Lock()
        self._running = False
        self._pipe_ready = threading.Event()

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True, name="HookIPC-Accept").start()
        if not self._pipe_ready.wait(timeout=5.0):
            self._logger.error("HookIPC 管道创建超时")
        else:
            self._logger.debug("HookIPC 服务端已启动，管道已就绪")

    def stop(self) -> None:
        self._running = False
        if self._pipe_ready.is_set():
            dummy = _ipc_kernel32.CreateFileW(
                self.PIPE_NAME, 0, 0, None, 3, 0, None
            )
            if dummy != _INVALID_HANDLE_VALUE:
                _ipc_kernel32.CloseHandle(dummy)
        with self._lock:
            for client in self._clients.values():
                _ipc_kernel32.CloseHandle(client.handle)
            self._clients.clear()
            self._listener_pid = None
            self._last_confirmed_pid = None

    def _accept_loop(self) -> None:
        while self._running:
            handle = _ipc_kernel32.CreateNamedPipeW(
                self.PIPE_NAME,
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
                PIPE_UNLIMITED_INSTANCES,
                self.BUFFER_SIZE,
                self.BUFFER_SIZE,
                0,
                None,
            )

            if handle == _INVALID_HANDLE_VALUE or handle is None:
                err = ctypes.get_last_error()
                self._logger.debug(f"CreateNamedPipeW 失败, err={err}")
                time.sleep(0.5)
                continue

            if not self._pipe_ready.is_set():
                self._pipe_ready.set()

            connected = _ipc_kernel32.ConnectNamedPipe(handle, None)
            if not connected and ctypes.get_last_error() != ERROR_PIPE_CONNECTED:
                _ipc_kernel32.CloseHandle(handle)
                continue

            threading.Thread(
                target=self._handle_client,
                args=(handle,),
                daemon=True,
                name="HookIPC-Client",
            ).start()

    def _label_locked(self, pid: Optional[int]) -> str:
        """格式化 pid + 标识，必须在持有 self._lock 时调用."""
        if pid is None:
            return "pid=?"
        client = self._clients.get(pid)
        if client:
            name = client.tag_name or client.tdata_name
            return f"pid={pid}({name})"
        return f"pid={pid}"

    def _handle_client(self, handle: int) -> None:
        pid: Optional[int] = None
        graceful = False

        while self._running:
            msg = self._read_message(handle)
            if msg is None:
                break

            if msg.startswith("REGISTER:"):
                try:
                    parts = msg.split(":", 2)
                    if len(parts) == 3:
                        tdata_name = parts[1]
                        pid = int(parts[2])
                        tag_name = self._tag_resolver(tdata_name) if self._tag_resolver else None
                        with self._lock:
                            self._clients[pid] = HookClient(
                                pid=pid, tdata_name=tdata_name, handle=handle, tag_name=tag_name,
                            )
                except (ValueError, IndexError):
                    self._logger.error(f"无效的 REGISTER 消息: {msg}")
                    break

            elif msg.startswith("LISTENING:"):
                pipe_name = msg.split(":", 1)[1]
                with self._lock:
                    old_pid = self._last_confirmed_pid
                    old_label = self._label_locked(old_pid)
                    if self._listener_pid and self._listener_pid in self._clients:
                        self._clients[self._listener_pid].is_listener = False
                    if pid and pid in self._clients:
                        self._clients[pid].is_listener = True
                        self._listener_pid = pid
                        self._last_confirmed_pid = pid
                    new_label = self._label_locked(pid)
                if old_pid and old_pid != pid:
                    self._logger.info(
                        f"监听者切换: {old_label} → {new_label}"
                    )
                self._logger.info(f"监听者就绪: {new_label}")

            elif msg == "NOT_LISTENING":
                pending_msg = None
                with self._lock:
                    if pid == self._listener_pid:
                        pending_msg = self._assign_next_locked()
                if pending_msg:
                    self._send_message(pending_msg[0], pending_msg[1])

            elif msg.startswith("URL_FOUND:"):
                url = msg.split(":", 1)[1]
                with self._lock:
                    label = self._label_locked(pid)
                self._logger.info(f"收到 URL: {url} (来自 {label})")
                try:
                    self._url_handler(url)
                except Exception as e:
                    self._logger.error(f"URL 处理失败: {e}")

            elif msg.startswith("BYE:"):
                graceful = True
                break

        self._on_disconnect(handle, pid, graceful=graceful)

    def _on_disconnect(self, handle: int, pid: Optional[int], graceful: bool = False) -> None:
        if pid is None:
            _ipc_kernel32.CloseHandle(handle)
            return

        with self._lock:
            client = self._clients.pop(pid, None)

        if not client:
            _ipc_kernel32.CloseHandle(handle)
            return

        label = f"pid={pid}({client.tag_name or client.tdata_name})"
        if graceful:
            self._logger.info(f"客户端退出: {label}, was_listener={client.is_listener}")
        else:
            self._logger.info(f"客户端异常断开: {label}, was_listener={client.is_listener}")

        pending_msg = None
        if self._listener_pid == pid:
            with self._lock:
                if self._listener_pid == pid:
                    self._listener_pid = None
                    pending_msg = self._assign_next_locked()
        if pending_msg:
            self._send_message(pending_msg[0], pending_msg[1])

        if self._exit_handler:
            try:
                self._exit_handler(pid)
            except Exception as e:
                self._logger.exception(f"exit_handler 执行失败: {e}")

        _ipc_kernel32.CloseHandle(handle)

    def _assign_next_locked(self) -> Optional[tuple[int, str]]:
        """选择下一个监听者，返回 (handle, message) 供调用者在锁外发送。"""
        if not self._clients:
            self._listener_pid = None
            return None

        failed_pid = self._listener_pid
        next_pid = None
        for candidate_pid in self._clients:
            if candidate_pid != failed_pid:
                next_pid = candidate_pid
                break

        if next_pid is None:
            self._listener_pid = None
            return None

        self._listener_pid = next_pid
        self._logger.info(f"新监听者: {self._label_locked(next_pid)}")
        return (self._clients[next_pid].handle, "RETRY_LISTEN")

    def _read_message(self, handle: int) -> Optional[str]:
        buf = ctypes.create_string_buffer(self.BUFFER_SIZE)
        bytes_read = wintypes.DWORD(0)

        success = _ipc_kernel32.ReadFile(
            handle, buf, self.BUFFER_SIZE, ctypes.byref(bytes_read), None
        )

        if not success or bytes_read.value == 0:
            return None

        try:
            return buf.raw[:bytes_read.value].decode("utf-16-le").rstrip("\x00")
        except Exception:
            return None

    def _send_message(self, handle: int, message: str) -> bool:
        data = (message + "\x00").encode("utf-16-le")
        bytes_written = wintypes.DWORD(0)

        success = _ipc_kernel32.WriteFile(
            handle, data, len(data), ctypes.byref(bytes_written), None
        )

        return bool(success)
