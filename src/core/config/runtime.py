"""运行时临时状态."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RuntimeState:
    """运行时状态数据."""

    start_time: Optional[datetime] = None
    tag: str = ""
    force_key_login: bool = False
    decrypted: bool = False
    password: str = ""
