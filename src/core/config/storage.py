"""
配置存储持久化。

实现 JSON 文件的原子写入策略（写入临时文件 -> fsync -> 替换），
并提供后台自动落盘线程。
"""
import json
import os
import threading
from contextlib import suppress
from pathlib import Path
from typing import Dict, Any, TYPE_CHECKING, Optional, Callable

from src.core.event_bus import get_event_bus, APP_COMPLETION
from src.core.runtime import delay

if TYPE_CHECKING:
    from .service import ConfigService


class ConfigStorage:
    """
    基于 JSON 的本地文件持久化存储。
    """

    def __init__(self, config_path: Path, default_config: Dict[str, Any],
                 error_handler: Optional[Callable[[str], None]] = None):
        self._config_path = config_path
        self._temp_file = config_path.with_suffix(".tmp")
        self._default_config = default_config
        self._save_lock = threading.RLock()

        self._save_thread_running = True
        self._config_changed = False
        self._batch = False
        self._config: Dict[str, Any] = {}
        self._error_handler = error_handler
        self._save_thread: Optional[threading.Thread] = None

    def load(self) -> Dict[str, Any]:
        """加载配置。若文件不存在或损坏，则用默认值初始化。"""
        try:
            if not self._config_path.exists():
                self.save(self._default_config)
                return self._default_config.copy()

            with open(self._config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if not isinstance(loaded, dict):
                    loaded = {}
                # 合并配置
                self._config = {**self._default_config, **loaded}
                return self._config.copy()
        except (json.JSONDecodeError, IOError):
            return self._default_config.copy()

    def _log_error(self, message: str) -> None:
        if self._error_handler:
            with suppress(Exception):
                self._error_handler(message)

    def save(self, configs: Dict[str, Any]) -> None:
        """原子落盘策略。"""
        with self._save_lock:
            try:
                self._config_path.parent.mkdir(parents=True, exist_ok=True)

                # 仅持久化定义在默认配置中的键
                to_save = {k: v for k, v in dict(configs).items() if k in self._default_config}

                with open(self._temp_file, "w", encoding="utf-8") as f:
                    json.dump(to_save, f, indent=4, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())  # 强制刷入磁盘

                os.replace(self._temp_file, self._config_path)
                self._config_changed = False
            except Exception as e:
                self._log_error(f"配置文件落盘失败: {e}")
            finally:
                with suppress(OSError):
                    if self._temp_file.exists():
                        self._temp_file.unlink()

    def start_auto_save(self, config_service: 'ConfigService') -> None:
        """启动后台线程，周期性检查是否需要保存。"""
        completion_event = threading.Event()

        def on_completion(_):
            completion_event.set()

        get_event_bus().subscribe(APP_COMPLETION, on_completion)

        def worker():
            while self._save_thread_running:
                with self._save_lock:
                    should_save = self._config_changed and not self._batch

                if should_save:
                    # noinspection PyProtectedMember
                    self.save(config_service._config)

                if completion_event.is_set():
                    break
                delay(5)

            get_event_bus().unsubscribe(APP_COMPLETION, on_completion)

        self._save_thread = threading.Thread(target=worker, daemon=True)
        self._save_thread.start()

    def stop_auto_save(self) -> None:
        """停止自动保存线程。"""
        self._save_thread_running = False
        if self._save_thread and self._save_thread.is_alive():
            self._save_thread.join(timeout=2.0)


class InMemoryConfigStorage:
    """仅存在于内存的配置存储（用于测试环境）。"""

    def __init__(self, default_config: Dict[str, Any]):
        self._config = default_config.copy()
        self._config_changed = False
        self._batch = False

    def load(self) -> Dict[str, Any]:
        return self._config.copy()

    def save(self, configs: Dict[str, Any]) -> None:
        self._config = dict(configs)
        self._config_changed = False

    def start_auto_save(self, config_service: 'ConfigService') -> None: pass

    def stop_auto_save(self) -> None: pass

    @property
    def config_path(self) -> Path: return Path(":memory:")

    @property
    def config_changed(self) -> bool: return self._config_changed

    @config_changed.setter
    def config_changed(self, v): self._config_changed = v

    @property
    def batch(self) -> bool: return self._batch

    @batch.setter
    def batch(self, v): self._batch = v
