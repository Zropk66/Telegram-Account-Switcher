"""
pytest 共享配置与通用 fixture。

每个测试都会自动重置全局单例和事件总线，避免用例之间共享状态。
"""
import os
import pytest
from unittest.mock import MagicMock, patch

# UI 测试在无显示器环境下运行
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_LOGGING_RULES"] = "*.debug=false"


@pytest.fixture(autouse=True)
def reset_singletons():
    """在每个测试前后重置全局状态，保证测试隔离。"""
    from src.core.logger import Logger, reset_logger_state
    from src.core.config import ConfigService
    from src.ui.popup import Popup
    from src.core.event_bus import EventBus, set_event_bus
    from src.core.process_manager import _set_should_reap
    from src.core.single_instance import SingleInstanceLock

    Logger.reset_instance()
    reset_logger_state()
    ConfigService.reset_instance()
    Popup.reset_instance()
    SingleInstanceLock.cleanup()

    test_bus = EventBus()
    set_event_bus(test_bus)

    _set_should_reap(False)

    yield

    Logger.reset_instance()
    reset_logger_state()
    ConfigService.reset_instance()
    Popup.reset_instance()
    SingleInstanceLock.cleanup()
    set_event_bus(None)
    _set_should_reap(True)


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """集中清理测试主动登记的临时文件或目录。"""
    temp_files = []

    yield temp_files

    for path in temp_files:
        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                import shutil
                shutil.rmtree(path)
        except Exception:
            pass


@pytest.fixture
def mock_config():
    """提供满足 IConfigProvider 协议的配置替身。"""
    from src.core.interfaces import IConfigProvider

    config = MagicMock(spec=IConfigProvider)

    config.client = "Telegram.exe"
    config.path = "/tmp/test_tas"
    config.default = "default_account"
    config.tags = {
        "account1": {
            "id": "12345",
            "folder": "tdata-abc",
            "info": "",
            "identity": "",
            "key": ""
        }
    }
    config.log_output = False
    config.agreed_to_decrypt = False

    config.tag = ""
    config.pwd = "test_password"
    config.decrypted = False
    config.force_key_login = False
    config.start_time = None

    config.has_backup = False
    config.configs = {}

    config.get_account.return_value = {"id": "12345", "folder": "tdata-abc"}
    config.has_complete_keys.return_value = False
    config.login_with_keys.return_value = True
    config.backup_account_keys.return_value = True
    config.sync_all_account_paths.return_value = None

    return config


@pytest.fixture
def mock_logger():
    """提供满足 ILogger 协议的日志器替身。"""
    from src.core.interfaces import ILogger
    return MagicMock(spec=ILogger)


@pytest.fixture
def mock_process_manager():
    """提供满足 IProcessManager 协议的进程管理器替身。"""
    from src.core.interfaces import IProcessManager
    manager = MagicMock(spec=IProcessManager)
    manager.start_process.return_value = True
    manager.kill_process.return_value = True

    from contextlib import contextmanager

    @contextmanager
    def mock_kill_and_guard(client_name, restart_on_exit=False):
        yield

    manager.kill_and_guard = mock_kill_and_guard

    return manager


@pytest.fixture
def mock_process():
    """提供内存进程服务，避免启动或终止真实进程。"""
    from src.core.process_service import MockProcessService
    return MockProcessService()


@pytest.fixture
def mock_account_fs():
    """提供账户文件系统替身。"""
    fs = MagicMock()
    fs.find_account_folder.return_value = "tdata-account1"
    fs.swap_active_tdata_with_target.return_value = True
    return fs


@pytest.fixture
def temp_dir(tmp_path):
    """为旧测试保留的 tmp_path 别名。"""
    return tmp_path


@pytest.fixture
def in_memory_config():
    """提供使用内存存储的 ConfigService，避免配置测试产生磁盘 I/O。"""
    from src.core.config import ConfigService, InMemoryConfigStorage

    ConfigService.reset_instance()
    config = ConfigService()
    storage = InMemoryConfigStorage(ConfigService._DEFAULT_CONFIG)
    config._storage = storage
    config._config = storage.load()
    config.__dict__['__initialized'] = True
    config.client = "Telegram.exe"
    config.path = "/tmp/test_tas"
    config.default = "test_account"
    config.tags = {}

    return config


@pytest.fixture(autouse=True)
def fast_delays():
    """跳过测试中的人为延迟，避免用例因 sleep 变慢。"""
    with patch('src.core.runtime.delay', return_value=None):
        yield


@pytest.fixture(scope="session")
def qapp():
    """提供 session 级 QApplication，供 Qt 组件测试复用。"""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield app

    app.processEvents()
