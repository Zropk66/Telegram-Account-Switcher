"""
运行时临时状态。

这些字段只描述当前进程会话，不参与配置文件持久化。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RuntimeState:
    """单次运行过程中的可变状态。"""

    start_time: Optional[datetime] = None
    tag: str = ""
    force_key_login: bool = False
    decrypted: bool = False
    password: str = ""
