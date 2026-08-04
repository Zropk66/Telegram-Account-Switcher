"""进程服务."""

from dataclasses import dataclass
from typing import List

import psutil


@dataclass
class ProcessInfo:
    """进程摘要信息."""

    pid: int
    name: str


@dataclass
class MockProcess:
    """模拟进程."""

    pid: int
    name: str
    alive: bool = True

    def terminate(self) -> None:
        """终止模拟进程."""
        self.alive = False

    def kill(self) -> None:
        """强制杀死模拟进程."""
        self.alive = False


class PsutilProcessService:
    """系统进程服务."""

    @staticmethod
    def find_processes(name: str) -> List[ProcessInfo]:
        """查找指定名称的进程."""
        processes = []
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                if proc.info.get("name") == name:
                    processes.append(ProcessInfo(pid=proc.info["pid"], name=proc.info["name"]))
        except Exception as e:
            from src.core.logger import Logger

            Logger().error(f"遍历系统进程列表时发生异常: {e}")
        return processes

    @staticmethod
    def _safe_op(pid: int, op: str) -> bool:
        """安全执行进程操作."""
        try:
            proc = psutil.Process(pid)
            getattr(proc, op)()
            return True
        except psutil.AccessDenied as e:
            from src.core.logger import Logger

            Logger().warning(f"对进程 PID={pid} 执行 {op} 操作时被拒绝 (AccessDenied): {e}")
            return False
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return False

    def terminate(self, pid: int) -> bool:
        """终止指定进程."""
        return self._safe_op(pid, "terminate")

    def kill(self, pid: int) -> bool:
        """强制杀死指定进程."""
        return self._safe_op(pid, "kill")

    @staticmethod
    def wait_for_process(pid: int, timeout: float) -> bool:
        """等待指定进程结束."""
        try:
            proc = psutil.Process(pid)
            return bool(not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return True


class MockProcessService:
    """模拟进程服务."""

    def __init__(self) -> None:
        """初始化模拟进程服务."""
        self._processes: List[MockProcess] = []
        self._next_pid = 1

    def add_process(self, name: str, pid: int = 0) -> MockProcess:
        """添加模拟进程."""
        if pid == 0:
            pid = self._next_pid
            self._next_pid += 1
        proc = MockProcess(pid=pid, name=name)
        self._processes.append(proc)
        return proc

    def find_processes(self, name: str) -> List[ProcessInfo]:
        """查找指定名称的模拟进程."""
        return [ProcessInfo(p.pid, p.name) for p in self._processes if p.name == name and p.alive]

    def terminate(self, pid: int) -> bool:
        """终止模拟进程."""
        for proc in self._processes:
            if proc.pid == pid and proc.alive:
                proc.terminate()
                return True
        return False

    def kill(self, pid: int) -> bool:
        """强制杀死模拟进程."""
        for proc in self._processes:
            if proc.pid == pid and proc.alive:
                proc.kill()
                return True
        return False

    @staticmethod
    def wait_for_process(pid: int, timeout: float) -> bool:
        """模拟等待指定进程结束."""
        return True
