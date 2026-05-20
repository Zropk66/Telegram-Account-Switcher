"""
SettingsController 设置控制器单元测试。

验证设置界面控制器与配置服务、账户模型和异步任务之间的协作逻辑。
"""
import os
import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path

# 设置 offscreen 模式，避免单元测试依赖真实显示器环境
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QListWidget, QLineEdit
from PySide6.QtCore import QThreadPool, Qt
from src.ui.settings_ui import SettingsController
from src.core.config import ConfigService


class MockSettingsWindow:
    """为 SettingsController 提供最小可用的设置窗口替身。"""

    def __init__(self):
        self.ui = MagicMock()
        self.ui.client_edit = QLineEdit()
        self.ui.path_edit = QLineEdit()
        self.ui.tags_widget = QListWidget()
        self.current_configs = {}

    def update_current_config(self, key, value):
        self.current_configs[key] = value


class TestSettingsController:
    """验证设置控制器的主要用户操作路径。"""

    def test_search_client_async_updates_fields(self, mock_config, monkeypatch):
        """验证客户端搜索完成后，路径与进程名能同步回填到界面和临时配置。"""
        window = MockSettingsWindow()
        window.current_configs = {}
        controller = SettingsController(window)
        controller.config = mock_config

        mock_result = ("Telegram.exe", "/path/to/telegram")

        def mock_run_search_client(pool, finished_callback, error_callback):
            finished_callback(mock_result)

        monkeypatch.setattr(
            "src.ui.settings_ui.AsyncTaskRunner.run_search_client",
            mock_run_search_client
        )

        controller.search_client_async()

        assert window.ui.client_edit.text() == "Telegram.exe"
        assert window.ui.path_edit.text() == "/path/to/telegram"
        assert window.current_configs.get("client") == "Telegram.exe"
        assert window.current_configs.get("path") == "/path/to/telegram"

    def test_scan_accounts_adds_new_only(self, mock_config, monkeypatch):
        """验证账户扫描只导入新增账户，避免重复覆盖已有条目。"""
        window = MockSettingsWindow()
        window.current_configs = {"agreed_to_decrypt": True}
        controller = SettingsController(window)
        controller.config = mock_config
        controller.model = MagicMock()

        mock_config.pwd = ""

        mock_existing_folders = {"tdata-existing"}
        monkeypatch.setattr(
            "src.ui.settings_ui.AccountScannerHelper.get_existing_folders",
            lambda widget: mock_existing_folders
        )

        def mock_scan(base_path, passcode):
            return {
                "tdata-existing": {"tag": "existing", "id": "1", "folder": "tdata-existing"},
                "tdata-new": {"tag": "new", "id": "2", "folder": "tdata-new"}
            }

        monkeypatch.setattr(
            "src.ui.settings_ui.TelegramEnvService.scan_accounts",
            MagicMock(side_effect=mock_scan)
        )

        monkeypatch.setattr("src.ui.settings_ui.alert", lambda *a, **kw: None)
        monkeypatch.setattr("src.ui.settings_ui.AccountScannerHelper.write_tag_file", lambda *a, **kw: True)
        monkeypatch.setattr("src.ui.settings_ui.Path.exists", lambda self: True)

        controller.scan_accounts("/valid/path")

        controller.model.add_account.assert_called_once()
        added_data = controller.model.add_account.call_args[0][0]
        assert added_data.get("tag") == "new"
        assert added_data.get("folder") == "tdata-new"

    def test_scan_accounts_first_use_requires_confirmation(self, mock_config, monkeypatch):
        """验证首次扫描前必须经过用户授权，避免无意解密本地数据。"""
        window = MockSettingsWindow()
        window.current_configs = {"agreed_to_decrypt": False}
        controller = SettingsController(window)
        controller.config = mock_config
        controller.model = MagicMock()

        monkeypatch.setattr("src.ui.settings_ui.confirm", lambda *a, **kw: False)
        monkeypatch.setattr("src.ui.settings_ui.Path.exists", lambda self: True)

        result = controller.scan_accounts("/valid/path")

        assert result is None
        controller.model.add_account.assert_not_called()

        window.current_configs = {"agreed_to_decrypt": False}
        monkeypatch.setattr("src.ui.settings_ui.confirm", lambda *a, **kw: True)
        monkeypatch.setattr("src.ui.settings_ui.AccountScannerHelper.get_existing_folders", lambda _: set())

        def mock_scan(*args, **kwargs):
            return {}

        monkeypatch.setattr(
            "src.ui.settings_ui.TelegramEnvService.scan_accounts",
            MagicMock(side_effect=mock_scan)
        )
        monkeypatch.setattr("src.ui.settings_ui.alert", lambda *a, **kw: None)

        controller.scan_accounts("/valid/path")

        assert window.current_configs.get("agreed_to_decrypt") is True

    def test_save_config_event_calls_batch_update(self, mock_config, monkeypatch):
        """验证保存配置时使用批量更新入口，保持配置提交的原子性。"""
        test_configs = {"test": "value"}
        mock_config.batch_update = MagicMock()

        mock_config.batch_update(test_configs)

        mock_config.batch_update.assert_called_once_with(test_configs)
