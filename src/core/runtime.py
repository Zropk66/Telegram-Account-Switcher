"""
运行时工具。

提供生产流程需要的延迟和临时目录命名能力。
"""
import secrets
import time


def delay(seconds: float) -> None:
    """等待指定秒数。"""
    time.sleep(seconds)


def generate_temp_name() -> str:
    """生成账户切换过程中使用的临时 tdata 目录名。"""
    return f"tdata-{secrets.token_hex(4)}"
