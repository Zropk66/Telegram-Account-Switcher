"""账户列表模型单元测试。"""
import os
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QApplication

from src.ui.settings_model import AccountListModel

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="module")
def qapp():
    """初始化 Qt 应用上下文，确保模型能够正确实例化。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


@pytest.fixture
def list_widget(qapp):
    """提供 UI 测试的 QListWidget 实例。"""
    return QListWidget()


@pytest.fixture
def mock_config():
    """提供 Mock 配置服务，隔离业务逻辑。"""
    config = MagicMock()
    config.default = "default_account"
    config.tags = {}
    config.get_all_accounts.return_value = {}
    return config


@pytest.fixture
def model(list_widget, mock_config):
    """提供初始化完成的 AccountListModel 实例。"""
    return AccountListModel(list_widget, mock_config)


def test_load_from_config_populates_list(model, list_widget, mock_config):
    """验证从配置文件加载账户列表后，UI 组件能正确填充项目。"""
    mock_config.get_all_accounts.return_value = {
        "account1": {"id": "123", "folder": "tdata1", "info": "", "identity": "", "key": ""},
        "account2": {"id": "456", "folder": "tdata2", "info": "", "identity": "", "key": ""}
    }

    model.load_from_config()

    assert list_widget.count() == 2

    item1 = list_widget.item(0)
    data1 = item1.data(Qt.UserRole)
    assert data1["tag"] == "account1"
    assert data1["id"] == "123"

    item2 = list_widget.item(1)
    data2 = item2.data(Qt.UserRole)
    assert data2["tag"] == "account2"
    assert data2["id"] == "456"


def test_add_account_syncs_to_config(model, list_widget, mock_config):
    """验证新增账户时，UI 列表更新且配置中心能够同步保存数据。"""
    account_data = {
        "tag": "new_account",
        "id": "789",
        "folder": "tdata_new",
        "info": "info_new",
        "identity": "identity_new",
        "key": "key_new"
    }

    model.add_account(account_data)

    assert list_widget.count() == 1
    assert mock_config.tags == {"new_account": {
        "id": "789",
        "folder": "tdata_new",
        "info": "info_new",
        "identity": "identity_new",
        "key": "key_new"
    }}


def test_remove_current_removes_from_config(model, list_widget, mock_config):
    """验证移除选中账户时，UI 与配置层级能够同步完成删除。"""
    mock_config.get_all_accounts.return_value = {
        "account1": {"id": "123", "folder": "tdata1", "info": "", "identity": "", "key": ""}
    }
    model.load_from_config()

    list_widget.setCurrentRow(0)
    result = model.remove_current()

    assert result is True
    assert list_widget.count() == 0
    assert mock_config.tags == {}


def test_refresh_display_marks_default(model, list_widget, mock_config):
    """验证刷新显示时，默认账户项能获得正确的 UI 标记。"""
    mock_config.default = "account1"
    mock_config.get_all_accounts.return_value = {
        "account1": {"id": "123", "folder": "tdata1", "info": "", "identity": "", "key": ""},
        "account2": {"id": "456", "folder": "tdata2", "info": "", "identity": "", "key": ""}
    }

    model.load_from_config()

    item1 = list_widget.item(0)
    assert "[默认]" in item1.text()

    item2 = list_widget.item(1)
    assert "[默认]" not in item2.text()


def test_sync_to_config_preserves_data_fields(model, list_widget, mock_config):
    """验证配置同步过程中，账户的所有业务字段都能完整保留。"""
    data = {
        "tag": "test_account",
        "id": "test_id",
        "folder": "test_folder",
        "info": "test_info",
        "identity": "test_identity",
        "key": "test_key"
    }
    list_widget.addItem("")
    item = list_widget.item(0)
    item.setData(Qt.UserRole, data)

    model.sync_to_config()

    assert "test_account" in mock_config.tags
    saved_data = mock_config.tags["test_account"]
    assert saved_data["id"] == "test_id"
    assert saved_data["folder"] == "test_folder"
    assert saved_data["info"] == "test_info"
    assert saved_data["identity"] == "test_identity"
    assert saved_data["key"] == "test_key"
