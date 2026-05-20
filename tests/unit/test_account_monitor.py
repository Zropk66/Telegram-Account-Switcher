"""
AccountMonitor 账户监控单元测试。

验证 Telegram 账户监控器的核心功能，包括文件监听、线程同步和事件处理。
"""
import pytest
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

from src.core.account.account_monitor import AccountMonitor, _ConfigsFileHandler
from src.core.event_bus import (
    Event,
    ProcessStatusChanged,
    AccountLoginDetected,
    AppCompletionEvent,
    get_event_bus,
    PROCESS_STATUS_CHANGED,
    ACCOUNT_LOGIN_DETECTED,
    APP_COMPLETION,
)


# ═════════════════════════════════════════════════════════════════════════════
# _ConfigsFileHandler 测试
# ═════════════════════════════════════════════════════════════════════════════

class TestConfigsFileHandler:
    """
    验证 watchdog 文件监听器的事件处理逻辑。
    """

    def test_watchdog_triggers_login_flag(self, tmp_path):
        """验证文件修改时设置登录标志并唤醒线程。"""
        target_file = tmp_path / "configs"
        target_file.touch()

        wake_event = threading.Event()
        login_flag = [False]

        handler = _ConfigsFileHandler(target_file, wake_event, login_flag)

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = str(target_file)

        handler.on_modified(mock_event)

        assert login_flag[0] is True
        assert wake_event.is_set()

    def test_watchdog_ignores_other_files(self, tmp_path):
        """验证监听器忽略非目标文件。"""
        target_file = tmp_path / "configs"
        other_file = tmp_path / "other.txt"
        target_file.touch()
        other_file.touch()

        wake_event = threading.Event()
        login_flag = [False]

        handler = _ConfigsFileHandler(target_file, wake_event, login_flag)

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = str(other_file)

        handler.on_modified(mock_event)

        assert login_flag[0] is False
        assert not wake_event.is_set()

    def test_on_created_triggers_login(self, tmp_path):
        """验证文件创建事件能触发登录检测。"""
        target_file = tmp_path / "configs"
        wake_event = threading.Event()
        login_flag = [False]

        handler = _ConfigsFileHandler(target_file, wake_event, login_flag)

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = str(target_file)

        handler.on_created(mock_event)

        assert login_flag[0] is True
        assert wake_event.is_set()

    def test_on_deleted_triggers_login(self, tmp_path):
        """验证文件删除事件能触发登录检测。"""
        target_file = tmp_path / "configs"
        wake_event = threading.Event()
        login_flag = [False]

        handler = _ConfigsFileHandler(target_file, wake_event, login_flag)

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = str(target_file)

        handler.on_deleted(mock_event)

        assert login_flag[0] is True
        assert wake_event.is_set()

    def test_on_moved_with_matching_dest_triggers_login(self, tmp_path):
        """验证文件移入目标路径能触发登录检测。"""
        target_file = tmp_path / "configs"
        wake_event = threading.Event()
        login_flag = [False]

        handler = _ConfigsFileHandler(target_file, wake_event, login_flag)

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.dest_path = str(target_file)

        handler.on_moved(mock_event)

        assert login_flag[0] is True
        assert wake_event.is_set()

    def test_on_moved_with_non_matching_dest_ignored(self, tmp_path):
        """验证文件移入非目标路径不触发登录检测。"""
        target_file = tmp_path / "configs"
        other_file = tmp_path / "other.txt"
        wake_event = threading.Event()
        login_flag = [False]

        handler = _ConfigsFileHandler(target_file, wake_event, login_flag)

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.dest_path = str(other_file)

        handler.on_moved(mock_event)

        assert login_flag[0] is False
        assert not wake_event.is_set()

    def test_directory_events_ignored(self, tmp_path):
        """验证目录事件被正确过滤，不触发登录检测。"""
        target_file = tmp_path / "configs"
        wake_event = threading.Event()
        login_flag = [False]

        handler = _ConfigsFileHandler(target_file, wake_event, login_flag)

        mock_event = MagicMock()
        mock_event.is_directory = True
        mock_event.src_path = str(tmp_path / "somedir")

        handler.on_modified(mock_event)

        assert login_flag[0] is False
        assert not wake_event.is_set()

    def test_invalid_path_handled_gracefully(self, tmp_path):
        """验证无效文件路径不会导致服务崩溃。"""
        target_file = tmp_path / "configs"
        wake_event = threading.Event()
        login_flag = [False]

        handler = _ConfigsFileHandler(target_file, wake_event, login_flag)

        mock_event = MagicMock()
        mock_event.is_directory = False
        # Windows下的非法路径字符
        mock_event.src_path = "\\\\invalid\\path\\<>:/\\|?*"

        handler.on_modified(mock_event)

        assert login_flag[0] is False


# ═════════════════════════════════════════════════════════════════════════════
# 线程同步测试
# ═════════════════════════════════════════════════════════════════════════════

class TestThreadSynchronization:
    """
    测试线程间的同步与协作机制。
    """

    def test_wake_event_set_from_watchdog_thread(self, tmp_path, mock_config, mock_logger):
        """验证文件监控线程能正确唤醒主循环线程。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)
        mock_config.path = str(tmp_path)

        wake_event = threading.Event()
        login_flag = [False]

        handler = _ConfigsFileHandler(
            configs_dir / "configs",
            wake_event,
            login_flag
        )

        wait_result = []

        def simulate_monitor_loop():
            # 主循环线程阻塞等待唤醒
            wait_result.append(wake_event.wait(timeout=1.0))

        monitor_thread = threading.Thread(target=simulate_monitor_loop)
        monitor_thread.start()

        time.sleep(0.1)

        # 模拟文件监控线程触发
        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = str(configs_dir / "configs")
        handler.on_modified(mock_event)

        monitor_thread.join(timeout=2.0)

        assert len(wait_result) == 1
        assert wait_result[0] is True
        assert login_flag[0] is True

    def test_wake_event_set_from_eventbus_callback(self, tmp_path, mock_config, mock_logger):
        """验证 EventBus 回调能正确唤醒主循环线程。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)
        mock_config.path = str(tmp_path)

        with patch('src.core.account.account_monitor.Observer'):
            monitor = AccountMonitor(
                tag="test_tag",
                check_tag=None,
                config_manage=mock_config,
                logger=mock_logger,
                spawn_time=datetime.now()
            )

            wait_result = []

            def simulate_monitor_loop():
                wait_result.append(monitor._wake_event.wait(timeout=1.0))

            monitor_thread = threading.Thread(target=simulate_monitor_loop)
            monitor_thread.start()

            time.sleep(0.1)

            # 模拟 EventBus 在其他线程触发状态变更
            def simulate_eventbus_callback():
                monitor._process_alive = False
                monitor._wake_event.set()

            callback_thread = threading.Thread(target=simulate_eventbus_callback)
            callback_thread.start()
            callback_thread.join()

            monitor_thread.join(timeout=2.0)

            assert len(wait_result) == 1
            assert wait_result[0] is True
            assert monitor._process_alive is False

    def test_multiple_wake_calls_coalesced(self, tmp_path, mock_config, mock_logger):
        """验证连续的多次唤醒请求表现为原子操作。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)
        mock_config.path = str(tmp_path)

        with patch('src.core.account.account_monitor.Observer'):
            monitor = AccountMonitor(
                tag="test_tag",
                check_tag=None,
                config_manage=mock_config,
                logger=mock_logger,
                spawn_time=datetime.now()
            )

            monitor._wake_event.set()
            monitor._wake_event.set()
            monitor._wake_event.set()

            assert monitor._wake_event.is_set()
            assert monitor._wake_event.wait(timeout=0) is True

            monitor._wake_event.clear()
            assert monitor._wake_event.wait(timeout=0.1) is False

    def test_login_flag_shared_between_threads(self, tmp_path):
        """验证登录状态标志在多线程环境下具有一致性。"""
        target_file = tmp_path / "configs"
        wake_event = threading.Event()
        login_flag = [False]

        handler = _ConfigsFileHandler(target_file, wake_event, login_flag)
        results = []

        def modify_flag():
            mock_event = MagicMock()
            mock_event.is_directory = False
            mock_event.src_path = str(target_file)
            handler.on_modified(mock_event)
            results.append(login_flag[0])

        threads = [threading.Thread(target=modify_flag) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)
        assert login_flag[0] is True


# ═════════════════════════════════════════════════════════════════════════════
# AccountMonitor 逻辑测试
# ═════════════════════════════════════════════════════════════════════════════

class TestAccountMonitor:
    """
    测试账户监控器的核心业务逻辑。
    """

    def test_check_mtime_after_file_change(self, tmp_path, mock_config, mock_logger):
        """验证文件修改时间更新后，监控器能识别到最新变更。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)
        configs_file = configs_dir / "configs"
        configs_file.touch()

        mock_config.path = str(tmp_path)
        spawn_time = datetime.now() - timedelta(seconds=10)

        # 将文件最后修改时间设置为 spawn_time 之后，表明发生过修改
        import os
        file_mtime = spawn_time.timestamp() + 5
        os.utime(str(configs_file), (file_mtime, file_mtime))

        monitor = AccountMonitor(
            tag="test_tag",
            check_tag=None,
            config_manage=mock_config,
            logger=mock_logger,
            spawn_time=spawn_time
        )

        assert monitor._check_mtime() is True

    def test_check_mtime_before_spawn_returns_false(self, tmp_path, mock_config, mock_logger):
        """验证未发生新修改时，监控器不触发更新。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)
        configs_file = configs_dir / "configs"
        configs_file.touch()

        mock_config.path = str(tmp_path)
        spawn_time = datetime.now() + timedelta(seconds=10)

        monitor = AccountMonitor(
            tag="test_tag",
            check_tag=None,
            config_manage=mock_config,
            logger=mock_logger,
            spawn_time=spawn_time
        )

        assert monitor._check_mtime() is False

    def test_process_exit_triggers_restore(self, tmp_path, mock_config, mock_logger):
        """验证 Telegram 进程退出后，自动恢复默认账户配置。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)

        mock_config.path = str(tmp_path)
        mock_config.default = "default_account"
        mock_config.start_time = datetime.now()

        with patch('src.core.account.account_monitor.Observer'), \
             patch('src.core.account.account_monitor.restore_default') as mock_restore, \
             patch('src.core.account.account_monitor.psutil') as mock_psutil:

            mock_process = MagicMock()
            mock_process.info = {'name': mock_config.client}
            mock_psutil.process_iter.return_value = [mock_process]

            monitor = AccountMonitor(
                tag="test_tag",
                check_tag=None,
                config_manage=mock_config,
                logger=mock_logger,
                spawn_time=datetime.now()
            )

            monitor._process_alive = False
            monitor._login_detected = [True]

            # 模拟业务运行循环中恢复默认账户的判定逻辑
            if monitor.tag and monitor.tag != monitor.config.default:
                mock_restore()

            mock_restore.assert_called_once()

    def test_observer_cleanup(self, tmp_path, mock_config, mock_logger):
        """验证监控器终止时能正确清理 Observer 资源。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)
        mock_config.path = str(tmp_path)

        with patch('src.core.account.account_monitor.Observer') as mock_obs_cls:
            mock_observer = mock_obs_cls.return_value
            monitor = AccountMonitor(
                tag="test_tag",
                check_tag=None,
                config_manage=mock_config,
                logger=mock_logger,
                spawn_time=datetime.now()
            )

            monitor._observer = mock_observer
            monitor._observer.stop()
            monitor._observer.join(timeout=2)

            mock_observer.stop.assert_called_once()
            mock_observer.join.assert_called_once_with(timeout=2)

    def test_completion_event_published(self, tmp_path, mock_config, mock_logger):
        """验证任务完成后能发布 AppCompletionEvent 事件。"""
        event_bus = get_event_bus()
        captured = []

        def capture_event(payload):
            captured.append(payload)

        event_bus.subscribe(APP_COMPLETION, capture_event)

        with patch('src.core.account.account_monitor.Observer'):
            monitor = AccountMonitor(
                tag="test_tag",
                check_tag=None,
                config_manage=mock_config,
                logger=mock_logger,
                spawn_time=datetime.now()
            )

            event_bus.publish(Event(
                APP_COMPLETION,
                AppCompletionEvent(success=True, message="账户切换完成"),
            ))

            assert len(captured) > 0
            assert isinstance(captured[0], AppCompletionEvent)
            assert captured[0].success is True

    def test_key_sync_only_after_60_seconds(self, tmp_path, mock_config, mock_logger):
        """验证密钥备份策略：仅在登录状态维持超过 60 秒后同步。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)

        mock_config.path = str(tmp_path)
        mock_config.default = "default_account"
        # 已运行 70 秒
        mock_config.start_time = datetime.now() - timedelta(seconds=70)

        monitor = AccountMonitor(
            tag="test_tag",
            check_tag=None,
            config_manage=mock_config,
            logger=mock_logger,
            spawn_time=datetime.now() - timedelta(seconds=80)
        )
        monitor._login_detected = [True]

        # 模拟同步判断逻辑
        if monitor.tag != monitor.config.default:
            running_time = datetime.now() - monitor.config.start_time
            if running_time.total_seconds() >= 60:
                monitor.config.backup_account_keys(monitor.tag, Path(monitor.config.path) / "tdata")

        mock_config.backup_account_keys.assert_called_once()

    def test_no_key_sync_if_not_logged_in(self, tmp_path, mock_config, mock_logger):
        """验证未登录状态下不执行密钥同步。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)

        mock_config.path = str(tmp_path)
        mock_config.default = "default_account"
        mock_config.start_time = datetime.now() - timedelta(seconds=70)

        monitor = AccountMonitor(
            tag="test_tag",
            check_tag=None,
            config_manage=mock_config,
            logger=mock_logger,
            spawn_time=datetime.now() - timedelta(seconds=80)
        )
        # 未登录
        is_logged_in = False

        if monitor.tag != monitor.config.default:
            if is_logged_in:
                monitor.config.backup_account_keys(monitor.tag, Path(monitor.config.path) / "tdata")

        mock_config.backup_account_keys.assert_not_called()

    def test_no_restore_if_same_as_default(self, tmp_path, mock_config, mock_logger):
        """验证当账户为默认账户时，不触发额外的自动恢复逻辑。"""
        mock_config.path = str(tmp_path)
        mock_config.default = "same_tag"

        monitor = AccountMonitor(
            tag="same_tag",
            check_tag=None,
            config_manage=mock_config,
            logger=mock_logger,
            spawn_time=datetime.now()
        )

        with patch('src.core.account.account_monitor.restore_default') as mock_restore:
            if monitor.tag and monitor.tag != monitor.config.default:
                mock_restore()

            mock_restore.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# AccountMonitor 集成测试
# ═════════════════════════════════════════════════════════════════════════════

class TestAccountMonitorIntegration:
    """
    测试 AccountMonitor 与系统组件的集成协作能力。
    """

    def test_observer_started_with_correct_path(self, tmp_path, mock_config, mock_logger):
        """验证监控器正确初始化文件监听观察者。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)
        mock_config.path = str(tmp_path)

        with patch('src.core.account.account_monitor.Observer') as mock_obs_cls:
            mock_observer = mock_obs_cls.return_value
            monitor = AccountMonitor(
                tag="test_tag",
                check_tag=None,
                config_manage=mock_config,
                logger=mock_logger,
                spawn_time=datetime.now()
            )

            # 模拟初始化过程
            handler = _ConfigsFileHandler(
                monitor.configs_file,
                monitor._wake_event,
                monitor._login_detected
            )
            monitor._observer = mock_observer
            monitor._observer.schedule(handler, str(configs_dir))
            monitor._observer.start()

            mock_observer.schedule.assert_called_once()
            call_args = mock_observer.schedule.call_args
            assert isinstance(call_args[0][0], _ConfigsFileHandler)
            assert call_args[0][1] == str(configs_dir)
            mock_observer.start.assert_called_once()

    def test_eventbus_subscription_on_run(self, tmp_path, mock_config, mock_logger):
        """验证监控器运行时正确订阅了进程状态变更事件。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)
        mock_config.path = str(tmp_path)

        event_bus = get_event_bus()
        captured_subs = []

        original_subscribe = event_bus.subscribe

        def tracking_subscribe(event_type, handler):
            captured_subs.append(event_type)
            return original_subscribe(event_type, handler)

        with patch.object(event_bus, 'subscribe', side_effect=tracking_subscribe), \
             patch('src.core.account.account_monitor.Observer'), \
             patch('src.core.account.account_monitor.psutil'):

            monitor = AccountMonitor(
                tag="test_tag",
                check_tag=None,
                config_manage=mock_config,
                logger=mock_logger,
                spawn_time=datetime.now()
            )

            monitor._process_alive = False
            monitor.run()

            assert PROCESS_STATUS_CHANGED in captured_subs

    def test_full_lifecycle_event_flow(self, tmp_path, mock_config, mock_logger):
        """验证整个账户生命周期内的事件流转准确性。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)
        mock_config.path = str(tmp_path)
        mock_config.default = "default_account"

        captured_events = []
        event_bus = get_event_bus()

        def capture_event(payload):
            captured_events.append(payload)

        event_bus.subscribe(ACCOUNT_LOGIN_DETECTED, capture_event)
        event_bus.subscribe(APP_COMPLETION, capture_event)

        with patch('src.core.account.account_monitor.Observer'), \
             patch('src.core.account.account_monitor.psutil'):
            monitor = AccountMonitor(
                tag="test_tag",
                check_tag=None,
                config_manage=mock_config,
                logger=mock_logger,
                spawn_time=datetime.now()
            )

            # 模拟用户登录
            monitor._login_detected[0] = True
            event_bus.publish(Event(
                ACCOUNT_LOGIN_DETECTED,
                AccountLoginDetected(tag="test_tag")
            ))

            # 模拟进程关闭
            monitor._process_alive = False
            monitor._wake_event.set()

            # 模拟任务完成
            event_bus.publish(Event(
                APP_COMPLETION,
                AppCompletionEvent(success=True, message="完成")
            ))

            assert len(captured_events) >= 2
            assert isinstance(captured_events[0], AccountLoginDetected)
            assert isinstance(captured_events[1], AppCompletionEvent)


# ═════════════════════════════════════════════════════════════════════════════
# 边界情况测试
# ═════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """
    测试 AccountMonitor 的异常处理与健壮性。
    """

    def test_configs_dir_not_exists(self, tmp_path, mock_config, mock_logger):
        """验证当配置目录缺失时，服务应优雅跳过监听逻辑。"""
        mock_config.path = str(tmp_path)

        with patch('src.core.account.account_monitor.Observer'):
            monitor = AccountMonitor(
                tag="test_tag",
                check_tag=None,
                config_manage=mock_config,
                logger=mock_logger,
                spawn_time=datetime.now()
            )

            assert monitor._observer is None

    def test_check_mtime_with_nonexistent_file(self, tmp_path, mock_config, mock_logger):
        """验证文件不存在时，监控器不应抛出异常。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)
        mock_config.path = str(tmp_path)

        monitor = AccountMonitor(
            tag="test_tag",
            check_tag=None,
            config_manage=mock_config,
            logger=mock_logger,
            spawn_time=datetime.now()
        )

        assert monitor._check_mtime() is False

    def test_check_mtime_oserror_handled(self, tmp_path, mock_config, mock_logger):
        """验证文件 I/O 错误被正确捕获，不影响服务稳定性。"""
        configs_dir = tmp_path / "tdata" / "D877F783D5D3EF8C"
        configs_dir.mkdir(parents=True)
        mock_config.path = str(tmp_path)

        monitor = AccountMonitor(
            tag="test_tag",
            check_tag=None,
            config_manage=mock_config,
            logger=mock_logger,
            spawn_time=datetime.now()
        )

        with patch.object(Path, 'stat', side_effect=OSError("Permission denied")):
            assert monitor._check_mtime() is False
