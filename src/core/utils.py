"""
通用工具函数。
"""
import contextlib
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional


@contextmanager
def atomic_rename(src: Path, dst: Path) -> Generator[None, None, None]:
    """原子重命名的安全包装。"""
    if not src.exists():
        yield
        return

    src.rename(dst)
    try:
        yield
    except Exception:
        if dst.exists() and not src.exists():
            with contextlib.suppress(Exception):
                dst.rename(src)
        raise


def search_file_in_dirs(directory: str | Path, tag_name: str) -> Optional[str]:
    """通过 tas_tag 标签定位账户目录。"""
    try:
        base_dir = Path(directory)
        if not base_dir.is_dir():
            return None

        for entry in base_dir.iterdir():
            if not entry.is_dir():
                continue
            tas_tag_file = entry / "tas_tag"
            if not tas_tag_file.is_file():
                continue
            with contextlib.suppress(OSError, UnicodeDecodeError):
                if tas_tag_file.read_text(encoding="utf-8").strip() == tag_name:
                    return entry.name
        return None
    except (OSError, PermissionError, FileNotFoundError):
        return None


def format_timedelta(delta) -> str:
    """将 timedelta 转换为人类可读的 'X时Y分Z秒' 格式。"""
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}时{minutes}分{seconds}秒"
