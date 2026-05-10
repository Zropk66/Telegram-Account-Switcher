# -*- coding: utf-8 -*-
# @File    : runtime.py
# @Time    : 2026/5/10 16:27
# @Author  : Zropk
"""配置存储管理 - 对应原 ConfigStorage 内部类"""
import os
import time
import json
from contextlib import suppress
from copy import deepcopy
from pathlib import Path
from threading import RLock, Thread
from typing import Dict, Any, TYPE_CHECKING, Optional, Callable

from src.modules.config.data import ConfigData

if TYPE_CHECKING:
    from .service import ConfigService


class ConfigStorage:
    """配置持久化管理"""

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
        self._error_handler = error_handler  # 错误处理回调，避免直接导入 Logger
        self._save_thread: Optional[Thread] = None  # 保存线程引用

    def load(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if not self._config_path.exists():
                self.save(self._default_config)

            with open(self._config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if not isinstance(loaded, dict):
                    loaded = {}
                self._config = {**self._default_config, **loaded}
                return self._config
        except (json.JSONDecodeError, IOError):
            self._config = self._default_config.copy()
            return self._config

    def _log_error(self, message: str) -> None:
        """记录错误，使用回调函数避免循环导入"""
        if self._error_handler:
            try:
                self._error_handler(message)
            except Exception:
                pass  # 如果回调失败，静默处理

    def save(self, configs: Dict[str, Any]) -> None:
        """持久化配置到文件"""
        with self._save_lock:
            try:
                self._config_path.parent.mkdir(parents=True, exist_ok=True)

                # 只保存持久化字段
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
                with suppress(OSError):
                    if self._temp_file.exists():
                        self._temp_file.unlink()

    def start_auto_save(self, config_service: 'ConfigService') -> None:
        """启动自动保存线程"""

        def auto_save_worker():
            while self._save_thread_running:
                if self._config_changed and not self._batch:
                    self.save(config_service._config)
                if config_service.complete:
                    break
                time.sleep(5)

        self._save_thread = Thread(target=auto_save_worker, daemon=True)
        self._save_thread.start()

    def stop_auto_save(self) -> None:
        """停止自动保存线程并等待其结束"""
        self._save_thread_running = False
        if self._save_thread is not None and self._save_thread.is_alive():
            self._save_thread.join(timeout=2.0)  # 最多等待2秒

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
