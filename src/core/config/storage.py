"""
配置持久化层

负责把内存中的配置字典写入 JSON 文件，以及从文件加载。
写文件时先写临时文件再原子替换，避免写到一半断电导致数据丢失。
后台有一个守护线程定期检查脏标记，有变更就自动落盘。
"""
import json
import os
import threading
import time
from contextlib import suppress
from pathlib import Path
from threading import RLock, Thread
from typing import Dict, Any, TYPE_CHECKING, Optional, Callable

from src.core.event_bus import (
    AppCompletionEvent,
    event_bus,
    APP_COMPLETION,
)

if TYPE_CHECKING:
    from .service import ConfigService


class ConfigStorage:
    """JSON 文件的读写与自动保存"""

    def __init__(self, config_path: Path, default_config: Dict[str, Any],
                 error_handler: Optional[Callable[[str], None]] = None):
        self._config_path = config_path
        self._temp_file = config_path.with_suffix(".tmp")
        self._default_config = default_config
        self._save_lock = RLock()
        self._save_thread_running = True
        self._config_changed = False
        self._batch = False
        self._config: Dict[str, Any] = {}
        self._error_handler = error_handler  # 用回调而不是直接导入 Logger，避免循环依赖
        self._save_thread: Optional[Thread] = None

    def load(self) -> Dict[str, Any]:
        """从 JSON 文件加载配置，文件不存在则用默认值初始化"""
        try:
            if not self._config_path.exists():
                self.save(self._default_config)

            with open(self._config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if not isinstance(loaded, dict):
                    loaded = {}
                # 用户配置覆盖默认值
                self._config = {**self._default_config, **loaded}
                return self._config
        except (json.JSONDecodeError, IOError):
            self._config = self._default_config.copy()
            return self._config

    def _log_error(self, message: str) -> None:
        """通过回调记录错误，避免直接依赖 Logger"""
        if self._error_handler:
            try:
                self._error_handler(message)
            except Exception:
                pass

    def save(self, configs: Dict[str, Any]) -> None:
        """
        把配置写入 JSON 文件

        流程：先写 .tmp 临时文件 -> fsync 确保落盘 -> 原子替换原文件。
        只保存 _default_config 中定义过的字段，忽略运行时数据。
        """
        with self._save_lock:
            try:
                self._config_path.parent.mkdir(parents=True, exist_ok=True)

                # 过滤掉不在默认配置里的字段
                config_to_save = {
                    k: v for k, v in dict(configs).items() if k in self._default_config
                }

                with open(self._temp_file, "w", encoding="utf-8") as f:
                    json.dump(config_to_save, f, indent=4, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

                os.replace(self._temp_file, self._config_path)
                self._config_changed = False
            except Exception as e:
                self._log_error(f"保存配置文件失败: {e}")
            finally:
                # 清理临时文件
                with suppress(OSError):
                    if self._temp_file.exists():
                        self._temp_file.unlink()

    def start_auto_save(self, config_service: 'ConfigService') -> None:
        """启动后台守护线程，每 5 秒检查一次脏标记，有变更就自动保存"""

        completion_event = threading.Event()

        def on_completion(payload: AppCompletionEvent):
            completion_event.set()

        event_bus.subscribe(APP_COMPLETION, on_completion)

        def auto_save_worker():
            while self._save_thread_running:
                if self._config_changed and not self._batch:
                    self.save(config_service._config)
                # 收到退出事件就结束线程
                if completion_event.is_set():
                    break
                time.sleep(5)
            event_bus.unsubscribe(APP_COMPLETION, on_completion)

        self._save_thread = Thread(target=auto_save_worker, daemon=True)
        self._save_thread.start()

    def stop_auto_save(self) -> None:
        """停止自动保存线程，最多等 2 秒"""
        self._save_thread_running = False
        if self._save_thread is not None and self._save_thread.is_alive():
            self._save_thread.join(timeout=2.0)

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def config_changed(self) -> bool:
        return self._config_changed

    @config_changed.setter
    def config_changed(self, value: bool):
        self._config_changed = value

    @property
    def batch(self) -> bool:
        return self._batch

    @batch.setter
    def batch(self, value: bool):
        self._batch = value
