import contextlib
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


@contextmanager
def atomic_rename(src: Path, dst: Path) -> Generator[None, None, None]:
    """
    原子重命名的安全包装。

    正常退出时保持重命名结果；出错时尝试还原，再向上抛出异常。
    """
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


def search_file_in_dirs(directory, tag_name):
    """在目录中查找 tas_tag 内容匹配 ``tag_name`` 的子文件夹，返回文件夹名。"""
    try:
        base_dir = Path(directory)
        if not base_dir.is_dir():
            return None

        for entry in base_dir.iterdir():
            if entry.is_dir():
                tas_tag_file = entry / "tas_tag"
                if tas_tag_file.is_file():
                    try:
                        if tas_tag_file.read_text(encoding="utf-8").strip() == tag_name:
                            return entry.name
                    except Exception:
                        pass
        return None
    except Exception:
        return None


def is_exists(base_path: str, target_tag: str) -> bool:
    """检查 ``base_path`` 下是否存在 tas_tag 匹配 ``target_tag`` 的文件夹。"""
    if not base_path or not target_tag:
        return False
    try:
        folder = Path(base_path)
        tas_tag_file = folder / "tas_tag"
        if tas_tag_file.is_file():
            try:
                if tas_tag_file.read_text(encoding="utf-8").strip() == target_tag:
                    return True
            except Exception:
                pass
        return False
    except (PermissionError, OSError):
        return False


def format_timedelta(delta):
    """把 timedelta 格式化成 ``X时Y分Z秒``。"""
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}时{minutes}分{seconds}秒"
