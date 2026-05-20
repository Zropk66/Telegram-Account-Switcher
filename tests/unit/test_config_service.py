"""
ConfigService 配置服务功能单元测试。

验证配置管理的生命周期，包括单例一致性、事务原子性更新、密钥校验及账户配置的增删改查。
"""

import pytest
from unittest.mock import patch


def test_singleton_returns_same_instance(in_memory_config):
    """验证 ConfigService 单例模式在多次获取时返回同一实例。"""
    from src.core.config import ConfigService

    config1 = ConfigService()
    config2 = ConfigService()
    config3 = ConfigService.get_instance()

    assert config1 is config2
    assert config2 is config3
    assert config1 is config3


def test_batch_update_commits_on_success(in_memory_config):
    """验证批量更新在成功执行后配置已即时同步。"""
    in_memory_config.client = "Telegram.exe"
    in_memory_config.default = "test"

    updates = {
        "client": "TelegramNew.exe",
        "default": "new_default",
        "log_output": False
    }

    in_memory_config.batch_update(updates)

    assert in_memory_config.client == "TelegramNew.exe"
    assert in_memory_config.default == "new_default"
    assert in_memory_config.log_output is False


def test_batch_update_rollback_on_exception(in_memory_config):
    """验证批量更新过程中若发生异常，配置状态会回滚，保持原子性。"""
    original_client = in_memory_config.client
    original_default = in_memory_config.default
    original_log = in_memory_config.log_output

    try:
        with in_memory_config:
            in_memory_config.client = "ShouldNotExist.exe"
            in_memory_config.default = "should_not_exist"
            in_memory_config.log_output = False
            raise ValueError("Test exception")
    except ValueError:
        pass

    assert in_memory_config.client == original_client
    assert in_memory_config.default == original_default
    assert in_memory_config.log_output == original_log


def test_has_complete_keys(in_memory_config):
    """验证只有在完整提供 identity/info/key 三组数据时才判定为具备完整登录凭证。"""
    # 无凭证账户
    in_memory_config.set_account("no_keys", {
        "id": "123",
        "folder": "tdata-no",
        "info": "",
        "identity": "",
        "key": ""
    })

    # 部分凭证账户
    in_memory_config.set_account("partial_keys", {
        "id": "456",
        "folder": "tdata-partial",
        "info": "some_info",
        "identity": "",
        "key": ""
    })

    # 完整凭证账户
    in_memory_config.set_account("full_keys", {
        "id": "789",
        "folder": "tdata-full",
        "info": "info_data",
        "identity": "identity_data",
        "key": "key_data"
    })

    assert in_memory_config.has_complete_keys("no_keys") is False
    assert in_memory_config.has_complete_keys("partial_keys") is False
    assert in_memory_config.has_complete_keys("full_keys") is True

    in_memory_config.tag = "full_keys"
    assert in_memory_config.has_backup is True


def test_account_crud(in_memory_config):
    """验证账户数据的增删改查逻辑完整性。"""
    assert in_memory_config.get_all_accounts() == {}
    assert in_memory_config.get_tag_list() == []

    # 添加
    account1 = {
        "id": "1001",
        "folder": "tdata-1001",
        "info": "info1",
        "identity": "identity1",
        "key": "key1"
    }
    in_memory_config.set_account("account1", account1)

    assert "account1" in in_memory_config.tags
    assert in_memory_config.get_account("account1") == account1
    assert in_memory_config.get_tag_list() == ["account1"]

    # 修改
    account1_updated = {
        "id": "1001",
        "folder": "tdata-1001-new",
        "info": "info1-updated",
        "identity": "identity1-updated",
        "key": "key1-updated"
    }
    in_memory_config.set_account("account1", account1_updated)
    assert in_memory_config.get_account("account1") == account1_updated

    # 获取缺失记录
    non_existent = in_memory_config.get_account("non_existent")
    assert non_existent["id"] == ""
    assert non_existent["folder"] == ""

    # 删除
    in_memory_config.remove_account("account1")
    assert "account1" not in in_memory_config.tags
    assert in_memory_config.get_tag_list() == []


def test_shutdown_saves_dirty_data(in_memory_config):
    """验证只有在配置有未保存变更时，退出才会触发落盘保存。"""
    # 模拟脏数据
    in_memory_config.client = "ModifiedClient.exe"
    in_memory_config._storage._config_changed = True

    with patch.object(in_memory_config._storage, "save") as mock_save:
        in_memory_config.shutdown()
        mock_save.assert_called_once_with(in_memory_config._config)

    # 验证干净数据不触发保存
    in_memory_config._storage._config_changed = False
    with patch.object(in_memory_config._storage, "save") as mock_save:
        in_memory_config.shutdown()
        mock_save.assert_not_called()
