"""
进程服务接口实现。

提供对 `psutil` 的封装，允许通过 IProcessService 接口注入进程行为，
以解决系统进程权限限制带来的单元测试难题。
"""
from dataclasses import dataclass
from typing import List

import psutil
from src.core.interfaces import ProcessInfo


@dataclass
class MockProcess:
    """内部使用的测试用进程模拟对象。"""
    pid: int
    name: str
    alive: bool = True

    def terminate(self):
        """terminate 方法。"""
        self.alive = False
    def kill(self):
        """kill 方法。"""
        self.alive = False


class PsutilProcessService:
    """真实操作系统进程服务。"""

    def find_processes(self, name: str) -> List[ProcessInfo]:
        """find_processes 方法。"""
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info.get('name') == name:
                    processes.append(ProcessInfo(pid=proc.info['pid'], name=proc.info['name']))
        except Exception:
            pass
        return processes

    @staticmethod
    def _safe_op(pid: int, op: str) -> bool:
        """内部方法：_safe_op。"""
        try:
            proc = psutil.Process(pid)
            getattr(proc, op)()
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False

    def terminate(self, pid: int) -> bool:
        """terminate 方法。"""
        return self._safe_op(pid, "terminate")
    def kill(self, pid: int) -> bool:
        """kill 方法。"""
        return self._safe_op(pid, "kill")

    def wait_for_process(self, pid: int, timeout: float) -> bool:
        """wait_for_process 方法。"""
        try:
            psutil.Process(pid).wait(timeout=timeout)
            return True
        except psutil.TimeoutExpired:
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return True


class MockProcessService:
    """内存中的进程模拟服务，用于单元测试。"""

    def __init__(self):
        """初始化。"""
        self._processes: List[MockProcess] = []
        self._next_pid = 1

    def add_process(self, name: str, pid: int = None) -> MockProcess:
        """add_process 方法。"""
        if pid is None:
            pid = self._next_pid
            self._next_pid += 1
        proc = MockProcess(pid=pid, name=name)
        self._processes.append(proc)
        return proc

    def find_processes(self, name: str) -> List[ProcessInfo]:
        """find_processes 方法。"""
        return [ProcessInfo(p.pid, p.name) for p in self._processes if p.name == name and p.alive]

    def terminate(self, pid: int) -> bool:
        """terminate 方法。"""
        for proc in self._processes:
            if proc.pid == pid and proc.alive:
                proc.terminate()
                return True
        return False

    def kill(self, pid: int) -> bool:
        """kill 方法。"""
        for proc in self._processes:
            if proc.pid == pid and proc.alive:
                proc.kill()
                return True
        return False

    def wait_for_process(self, pid: int, timeout: float) -> bool:
        """wait_for_process 方法。"""
        return True
