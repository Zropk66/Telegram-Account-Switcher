"""
通用工具函数。
"""
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from src.core.constants import TAG_FILE
from src.core.logger import Logger


@contextmanager
def safe_rename(src: Path, dst: Path) -> Generator[None, None, None]:
    """安全重命名目录。"""
    if not src.exists():
        yield
        return

    src.rename(dst)
    try:
        yield
    except Exception:
        if dst.exists() and not src.exists():
            try:
                dst.rename(src)
            except Exception as rename_err:
                Logger().error(f"工具函数重命名回滚失败: {rename_err}")
        raise


def search_file_in_dirs(directory: str | Path, tag_name: str) -> Optional[str]:
    """搜索包含指定标签的目录。"""
    try:
        base_dir = Path(directory)
        if not base_dir.is_dir():
            return None

        for entry in base_dir.iterdir():
            if not entry.is_dir():
                continue
            tas_tag_file = entry / TAG_FILE
            if not tas_tag_file.is_file():
                continue
            try:
                if tas_tag_file.read_text(encoding="utf-8").strip() == tag_name:
                    return entry.name
            except (OSError, UnicodeDecodeError) as e:
                from src.core.logger import Logger
                Logger().warning(f"工具函数读取或解析目录 {entry.name} 中的 {TAG_FILE} 失败: {e}")
        return None
    except OSError as e:
        from src.core.logger import Logger
        Logger().error(f"工具函数遍历账户目录失败: {e}")
        return None


def format_timedelta(delta) -> str:
    """格式化时间差为中文文本。"""
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}时{minutes}分{seconds}秒"
