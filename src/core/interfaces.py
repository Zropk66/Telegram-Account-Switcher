"""
核心抽象接口定义。

使用 Protocol (结构化子类型) 定义系统各组件的契约。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProcessInfo:
    """跨平台的进程摘要信息。"""
    pid: int
    name: str
