"""测试共享配置与 Fixture。"""
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_LOGGING_RULES"] = "*.debug=false"


@pytest.fixture(autouse=True)
def reset_singletons():
    """在每个测试前后重置全局状态，保证测试隔离。"""
    from src.core.logger import Logger, reset_logger_state
    from src.core.config import ConfigService
    from src.ui.popup import Popup
    from src.core.process_manager import _set_should_reap
    from src.core.single_instance import SingleInstanceLock

    Logger.reset_instance()
    reset_logger_state()
    ConfigService.reset_instance()
    Popup.reset_instance()
    SingleInstanceLock.cleanup()

    _set_should_reap(False)

    yield

    Logger.reset_instance()
    reset_logger_state()
    ConfigService.reset_instance()
    Popup.reset_instance()
    SingleInstanceLock.cleanup()
    _set_should_reap(True)


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """清理测试临时文件。"""
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
    """提供满足 ConfigService 接口的配置替身。"""
    from src.core.config import ConfigService

    config = MagicMock(spec=ConfigService)

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
    """提供满足 Logger 接口的日志器替身。"""
    from src.core.logger import Logger
    return MagicMock(spec=Logger)


@pytest.fixture
def mock_process_manager():
    """提供满足 ProcessManager 接口的进程管理器替身。"""
    from src.core.process_manager import ProcessManager
    manager = MagicMock(spec=ProcessManager)
    manager.start_process.return_value = True
    manager.kill_process.return_value = True

    from contextlib import contextmanager

    @contextmanager
    def mock_kill_and_guard(client_name, restart_on_exit=False):
        """模拟守护进程上下文。"""
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
    fs.repoint_tdata_link.return_value = True
    fs.get_tdata_link_target.return_value = None
    fs.is_tdata_link.return_value = False
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
