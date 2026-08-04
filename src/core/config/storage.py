"""本地配置文件持久化（JSON）."""

import json
import os
import tempfile
import threading
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

if TYPE_CHECKING:
    pass


class ConfigStorage:
    """本地配置存储器."""

    def __init__(
        self, config_path: Path, default_config: Dict[str, Any], error_handler: Optional[Callable[[str], None]] = None
    ) -> None:
        """初始化 JSON 配置存储器."""
        self._config_path = config_path
        self._default_config = default_config
        self._lock = threading.Lock()

        self._config_changed = False
        self._batch = False
        self._config: Dict[str, Any] = {}
        self._error_handler = error_handler

    def load(self) -> Dict[str, Any]:
        """从文件加载配置."""
        try:
            if not self._config_path.exists():
                self.save(self._default_config)
                return self._default_config.copy()

            with open(self._config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if not isinstance(loaded, dict):
                    loaded = {}
                self._config = {**self._default_config, **loaded}
                return self._config.copy()
        except (json.JSONDecodeError, IOError):
            return self._default_config.copy()

    def _log_error(self, message: str) -> None:
        """记录错误信息."""
        if self._error_handler:
            with suppress(Exception):
                self._error_handler(message)

    def save(self, configs: Dict[str, Any]) -> None:
        """保存配置到文件."""
        with self._lock:
            temp_file = None
            try:
                self._config_path.parent.mkdir(parents=True, exist_ok=True)

                to_save = {k: v for k, v in dict(configs).items() if k in self._default_config}

                fd, temp_path_str = tempfile.mkstemp(
                    dir=str(self._config_path.parent), prefix="configs-", suffix=".json.tmp", text=True
                )
                temp_file = Path(temp_path_str)

                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(to_save, f, indent=4, ensure_ascii=False)
                    f.flush()

                os.replace(temp_file, self._config_path)
                temp_file = None
                self._config_changed = False
            except Exception as e:
                self._log_error(f"配置文件落盘失败: {e}")
            finally:
                if temp_file is not None:
                    with suppress(OSError):
                        if temp_file.exists():
                            temp_file.unlink()


class InMemoryConfigStorage:
    """内存配置存储器."""

    def __init__(self, default_config: Dict[str, Any]) -> None:
        """初始化内存配置存储器."""
        self._config = default_config.copy()
        self._config_changed = False
        self._batch = False

    def load(self) -> Dict[str, Any]:
        """加载内存中的配置."""
        return self._config.copy()

    def save(self, configs: Dict[str, Any]) -> None:
        """保存配置到内存."""
        self._config = dict(configs)
        self._config_changed = False

    @property
    def config_path(self) -> Path:
        """获取内存配置存储路径."""
        return Path(":memory:")

    @property
    def config_changed(self) -> bool:
        """获取配置变更状态."""
        return self._config_changed

    @config_changed.setter
    def config_changed(self, v: bool) -> None:
        """设置配置变更状态."""
        self._config_changed = v

    @property
    def batch(self) -> bool:
        """获取批量更新状态."""
        return self._batch

    @batch.setter
    def batch(self, v: bool) -> None:
        """设置批量更新状态."""
        self._batch = v
