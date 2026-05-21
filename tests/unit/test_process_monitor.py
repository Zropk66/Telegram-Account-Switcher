"""
ProcessMonitor 进程监控单元测试。

验证进程监控器的核心功能，包括进程状态检测和事件发布。
"""
import pytest
import time
from unittest.mock import MagicMock, patch, call

from src.core.process_manager import ProcessMonitor


class TestProcessMonitor:
    """
    进程生命周期监控的单元测试。
    """

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
        # 初始状态：进程未运行
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

            # 模拟进程被创建
            mock_process = MagicMock()
            mock_process.pid = 1234
            mock_process.name = 'Telegram.exe'
            mock_process_service.find_processes.return_value = [mock_process]

            time.sleep(0.1)

            # 检查是否已调用状态为存活的回调
            calls = mock_callback.call_args_list
            alive_calls = [c for c in calls if c[0][0] is True]

            assert len(alive_calls) > 0, "未能检测到进程启动回调"

        finally:
            monitor.stop_watching()

    def test_monitor_detects_process_exit(self, mock_callback, mock_process_service):
        """验证进程退出后能准确检测并触发回调。"""
        # 初始状态：进程已运行
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

        # 初始时，wait_for_process 模拟超时，表示进程仍在运行
        mock_process_service.wait_for_process.return_value = False

        monitor.start_watching()

        try:
            time.sleep(0.1)

            # 模拟进程终止 (wait_for_process 返回 True)
            mock_process_service.wait_for_process.return_value = True
            
            # 为了防止死循环或者过快触发，我们先让 find_processes 返回空
            mock_process_service.find_processes.return_value = []

            time.sleep(0.15)

            # 检查是否已调用状态为终止的回调
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
        
        # 模拟等待进程结束（也就是进程死了，返回 True）
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
