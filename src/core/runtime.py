"""运行时工具."""

import secrets
import time


def delay(seconds: float) -> None:
    """等待指定秒数."""
    time.sleep(seconds)


def generate_temp_name() -> str:
    """生成临时目录名."""
    return f"tdata-{secrets.token_hex(4)}"
