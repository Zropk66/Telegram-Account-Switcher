"""
测试用 Mock 实现。

这些类用于在单元测试和集成测试中替代外部副作用组件，并记录关键调用以便断言。
"""
from pathlib import Path
from typing import Dict, Any, List, Callable


class MockAccountRecoveryService:
    """记录账户恢复服务调用，并允许测试控制恢复结果。"""

    def __init__(self, logger=None):
        self.logger = logger
        self.cleanup_called = False
        self.cleanup_base_path = None
        self.recover_called = False
        self.recover_tag = None
        self.recover_config = None
        self.recover_result = True
        self.recover_error = None

    def cleanup_orphan_folders(self, base_path_str: str) -> None:
        """记录孤立目录清理请求，不执行真实文件操作。"""
        self.cleanup_called = True
        self.cleanup_base_path = base_path_str

    def recover_account(self, tag: str, config_manage) -> bool:
        """记录账户恢复请求，并返回测试预设结果。"""
        self.recover_called = True
        self.recover_tag = tag
        self.recover_config = config_manage

        if self.recover_error:
            raise self.recover_error
        return self.recover_result


class MockAccountMonitor:
    """替代 AccountMonitor，避免测试启动真实后台监控。"""

    def __init__(self, tag: str, check_tag: str, config, logger, spawn_time=None):
        self.tag = tag
        self.check_tag = check_tag
        self.config = config
        self.logger = logger
        self.spawn_time = spawn_time

        self.run_called = False
        self.login_detected = False
        self.process_exited = False

    def run(self) -> None:
        """记录监控器启动请求。"""
        self.run_called = True

    def simulate_login(self) -> None:
        """为测试手动标记已检测到登录。"""
        self.login_detected = True

    def simulate_exit(self) -> None:
        """为测试手动标记进程已退出。"""
        self.process_exited = True


class MockEventBus:
    """内存事件总线替身，用于验证事件发布与订阅行为。"""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._published_events: List[Any] = []

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """注册事件处理器。"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """移除事件处理器，未注册时保持幂等。"""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass

    def publish(self, event) -> None:
        """记录事件并同步通知当前订阅者。"""
        self._published_events.append(event)

        if event.type in self._subscribers:
            for handler in self._subscribers[event.type]:
                try:
                    handler(event.payload)
                except Exception:
                    pass

    def clear(self) -> None:
        """清空订阅和已发布事件记录。"""
        self._subscribers.clear()
        self._published_events.clear()

    def get_published_events(self, event_type: str = None) -> List[Any]:
        """返回已发布事件，可按事件类型过滤。"""
        if event_type is None:
            return list(self._published_events)
        return [e for e in self._published_events if e.type == event_type]


class MockFileSystem:
    """轻量级内存文件系统，供需要文件语义但不应触碰磁盘的测试使用。"""

    def __init__(self):
        self._files: Dict[str, bytes] = {}
        self._dirs: set = {"/"}

    def _normalize(self, path: Path | str) -> str:
        """将路径规整为内部统一格式。"""
        p = str(path)
        if not p.startswith("/"):
            p = "/" + p
        return p.rstrip("/")

    def exists(self, path: Path | str) -> bool:
        """判断路径是否存在。"""
        p = self._normalize(path)
        return p in self._files or p in self._dirs

    def is_dir(self, path: Path | str) -> bool:
        """判断路径是否为目录。"""
        p = self._normalize(path)
        return p in self._dirs

    def is_file(self, path: Path | str) -> bool:
        """判断路径是否为文件。"""
        p = self._normalize(path)
        return p in self._files

    def mkdir(self, path: Path | str, parents=True, exist_ok=True) -> None:
        """创建目录，默认自动补齐父目录。"""
        p = self._normalize(path)
        if parents:
            parts = p.split("/")
            for i in range(1, len(parts) + 1):
                self._dirs.add("/".join(parts[:i]))
        else:
            if not exist_ok and p in self._dirs:
                raise FileExistsError(p)
            self._dirs.add(p)

    def write_file(self, path: Path | str, data: bytes) -> None:
        """写入文件，并按需创建父目录。"""
        p = self._normalize(path)
        parent = str(Path(p).parent)
        if parent not in self._dirs:
            self.mkdir(parent, parents=True)
        self._files[p] = data

    def read_file(self, path: Path | str) -> bytes:
        """读取文件内容，文件缺失时抛出 FileNotFoundError。"""
        p = self._normalize(path)
        if p not in self._files:
            raise FileNotFoundError(p)
        return self._files[p]

    def list_dir(self, path: Path | str) -> List[str]:
        """列出指定目录下的一级文件和目录。"""
        p = self._normalize(path)
        if p != "":
            p += "/"
        return [
            name for name in self._files.keys()
            if name.startswith(p) and "/" not in name[len(p):]
        ] + [
            name for name in self._dirs
            if name.startswith(p) and name != p and "/" not in name[len(p):]
        ]

    def remove(self, path: Path | str) -> None:
        """删除文件或目录，路径不存在时抛出 FileNotFoundError。"""
        p = self._normalize(path)
        if p in self._files:
            del self._files[p]
        elif p in self._dirs:
            self._dirs.discard(p)
        else:
            raise FileNotFoundError(p)

    def rename(self, src: Path | str, dst: Path | str) -> None:
        """重命名文件或目录，源路径不存在时抛出 FileNotFoundError。"""
        s = self._normalize(src)
        d = self._normalize(dst)
        if s in self._files:
            self._files[d] = self._files.pop(s)
        elif s in self._dirs:
            self._dirs.discard(s)
            self._dirs.add(d)
        else:
            raise FileNotFoundError(src)
