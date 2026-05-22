"""进程监控单元测试。"""
import time
from unittest.mock import MagicMock, patch

import pytest

from src.core.process_manager import ProcessMonitor


class TestProcessMonitor:
    """进程生命周期监控的单元测试。"""

    @pytest.fixture
    def mock_callback(self):
        """提供 Mock 回调。"""
        return MagicMock()

    @pytest.fixture
    def mock_process_service(self):
        """Mock PsutilProcessService 模块。"""
        with patch('src.core.process_manager.PsutilProcessService') as mock:
            yield mock.return_value

    def test_monitor_detects_process_start(self, mock_callback, mock_process_service):
        """验证进程启动后能准确检测并触发回调。"""
        mock_process_service.find_processes.return_value = []

        monitor = ProcessMonitor(
            "Telegram.exe",
            check_interval=0.01,
            process_service=mock_process_service
        )
        monitor.register_callback(mock_callback)

        monitor.start_watching()

        try:
            time.sleep(0.05)

            mock_process = MagicMock()
            mock_process.pid = 1234
            mock_process.name = 'Telegram.exe'
            mock_process_service.find_processes.return_value = [mock_process]

            time.sleep(0.1)

            calls = mock_callback.call_args_list
            alive_calls = [c for c in calls if c[0][0] is True]

            assert len(alive_calls) > 0, "未能检测到进程启动回调"

        finally:
            monitor.stop_watching()

    def test_monitor_detects_process_exit(self, mock_callback, mock_process_service):
        """验证进程退出后能准确检测并触发回调。"""
        mock_process = MagicMock()
        mock_process.pid = 1234
        mock_process.name = 'Telegram.exe'
        mock_process_service.find_processes.return_value = [mock_process]

        monitor = ProcessMonitor(
            "Telegram.exe",
            check_interval=0.01,
            process_service=mock_process_service
        )
        monitor.register_callback(mock_callback)

        mock_process_service.wait_for_process.return_value = False

        monitor.start_watching()

        try:
            time.sleep(0.1)
            mock_process_service.wait_for_process.return_value = True
            mock_process_service.find_processes.return_value = []
            time.sleep(0.15)
            calls = mock_callback.call_args_list
            dead_calls = [c for c in calls if c[0][0] is False]

            assert len(dead_calls) > 0, "未能检测到进程退出回调"

        finally:
            monitor.stop_watching()

    def test_monitor_zero_cpu_when_process_alive(self, mock_process_service):
        """验证存活监控利用 process_service.wait_for_process。"""
        monitor = ProcessMonitor(
            "Telegram.exe",
            check_interval=0.5,
            process_service=mock_process_service
        )

        monitor.last_PID = 1234
        mock_process_service.wait_for_process.return_value = True
        result = monitor._wait_for_process_change(last_status=True)
        mock_process_service.wait_for_process.assert_called_once_with(1234, timeout=1.0)
        assert result is False

    def test_monitor_start_already_running(self):
        """验证监控器不可重入，防止状态污染。"""
        monitor = ProcessMonitor("Telegram.exe")

        monitor.start_watching()

        try:
            with pytest.raises(RuntimeError, match="进程监视器已启动"):
                monitor.start_watching()
        finally:
            monitor.stop_watching()

    def test_monitor_context_manager(self, mock_callback):
        """验证 watch() 上下文管理器能否自动注册/注销回调，并启动/停止监视。"""
        monitor = ProcessMonitor("Telegram.exe", check_interval=0.1)

        with patch.object(monitor, 'start_watching') as mock_start, \
             patch.object(monitor, 'stop_watching') as mock_stop, \
             patch.object(monitor, 'register_callback') as mock_register, \
             patch.object(monitor, 'unregister_callback') as mock_unregister:

            with monitor.watch(mock_callback) as m:
                assert m is monitor
                mock_register.assert_called_once_with(mock_callback)
                mock_start.assert_called_once()
                mock_unregister.assert_not_called()
                mock_stop.assert_not_called()

            mock_unregister.assert_called_once_with(mock_callback)
            mock_stop.assert_called_once()

