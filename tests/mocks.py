"""测试模拟对象。"""
from pathlib import Path
from typing import Dict, List


class MockAccountRecoveryService:
    """记录账户恢复服务调用，并允许测试控制恢复结果。"""

    def __init__(self, logger=None):
        """初始化模拟账户恢复服务。"""
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
        """初始化模拟账户监控器。"""
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


class MockFileSystem:
    """轻量级内存文件系统，供需要文件语义但不应触碰磁盘的测试使用。"""

    def __init__(self):
        """初始化模拟文件系统。"""
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
