# -*- coding: utf-8 -*-
# @File    : runtime.py
# @Time    : 2026/5/10 16:29
# @Author  : Zropk
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RuntimeState:
    """运行时状态 - 单一职责：管理临时状态"""

    start_time: Optional[datetime] = None
    tag: str = ""
    force_key_login: bool = False
    process_status: bool = False
    complete: bool = False
    decrypted: bool = False
    password: str = ""  # 注意：考虑安全存储
    has_backup: bool = False

    def reset(self) -> None:
        """重置运行时状态"""
        self.start_time = None
        self.tag = ""
        self.force_key_login = False
        self.process_status = False
        self.complete = False
        self.decrypted = False
        self.password = ""
        self.has_backup = False
