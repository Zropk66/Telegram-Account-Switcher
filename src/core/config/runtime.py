"""
运行时临时状态

存放只在当次运行期间有意义的变量，不参与持久化。
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RuntimeState:
    """单次运行过程中的临时状态"""

    start_time: Optional[datetime] = None
    tag: str = ""
    force_key_login: bool = False
    decrypted: bool = False
    password: str = ""  # TODO: 考虑用更安全的方式存储
    has_backup: bool = False

    def reset(self) -> None:
        """把所有字段恢复到初始值，用于切换账户时清理状态"""
        self.start_time = None
        self.tag = ""
        self.force_key_login = False
        self.decrypted = False
        self.password = ""
        self.has_backup = False
