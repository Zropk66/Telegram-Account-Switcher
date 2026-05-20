"""
ProcessMonitor 进程监控单元测试。

验证进程监控器的核心功能，包括进程状态检测和事件发布。
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch, call

from src.core.process_manager import ProcessMonitor
from src.core.event_bus import (
    ProcessStatusChanged,
    PROCESS_STATUS_CHANGED,
)


class TestProcessMonitor:
    """
    进程生命周期异步监控的单元测试。
    """

    @pytest.fixture
    def mock_event_bus(self):
        """提供 Mock 事件总线实例。"""
        return MagicMock()

    @pytest.fixture
    def mock_psutil(self):
        """Mock psutil 模块以隔离系统进程 API。"""
        with patch('src.core.process_manager.psutil') as mock:
            yield mock

    @pytest.fixture
    def mock_kernel32(self):
        """Mock Windows Kernel API 以模拟进程句柄等待。"""
        with patch('src.core.process_manager.kernel32') as mock:
            # 默认返回超时，模拟进程仍在运行
            mock.OpenProcess.return_value = 0x1234
            mock.WaitForSingleObject.return_value = 0x00000102  # WAIT_TIMEOUT
            mock.CloseHandle.return_value = True
            yield mock

    @pytest.mark.asyncio
    async def test_monitor_detects_process_start(self, mock_event_bus, mock_psutil):
        """验证进程启动后能准确检测并发布状态变更事件。"""
        # 初始状态：进程未运行
        mock_psutil.process_iter.return_value = []

        monitor = ProcessMonitor(
            "Telegram.exe",
            check_interval=0.01,
            event_bus=mock_event_bus
        )

        await monitor.start_watching()

        try:
            await asyncio.sleep(0.05)

            # 模拟进程被创建
            mock_process = MagicMock()
            mock_process.info = {'name': 'Telegram.exe', 'pid': 1234}
            mock_psutil.process_iter.return_value = [mock_process]

            await asyncio.sleep(0.1)

            # 检查是否已发布状态为存活的事件
            published_events = mock_event_bus.publish.call_args_list
            process_alive_events = [
                call for call in published_events
                if call[0][0].payload.is_alive
            ]

            assert len(process_alive_events) > 0, "未能检测到进程启动事件"

        finally:
            await monitor.stop_watching()

    @pytest.mark.asyncio
    async def test_monitor_detects_process_exit(self, mock_event_bus, mock_psutil, mock_kernel32):
        """验证进程退出后能准确检测并发布终止事件。"""
        # 初始状态：进程已运行
        mock_process = MagicMock()
        mock_process.info = {'name': 'Telegram.exe', 'pid': 1234}
        mock_psutil.process_iter.return_value = [mock_process]

        monitor = ProcessMonitor(
            "Telegram.exe",
            check_interval=0.01,
            event_bus=mock_event_bus
        )

        await monitor.start_watching()

        try:
            await asyncio.sleep(0.1)

            # 模拟进程终止 (WAIT_OBJECT_0)
            mock_kernel32.WaitForSingleObject.return_value = 0
            monitor.last_PID = 1234

            await asyncio.sleep(0.15)

            # 检查是否已发布状态为终止的事件
            published_events = mock_event_bus.publish.call_args_list
            process_dead_events = [
                call for call in published_events
                if not call[0][0].payload.is_alive
            ]

            assert len(process_dead_events) > 0, "未能检测到进程退出事件"

        finally:
            await monitor.stop_watching()

    def test_find_process_id_uses_process_iter_pid_info(self, mock_psutil):
        """从 psutil 进程快照中读取 pid，避免 Mock 属性泄漏到 Win32 API。"""
        mock_process = MagicMock()
        mock_process.info = {'name': 'Telegram.exe', 'pid': 1234}
        mock_psutil.process_iter.return_value = [mock_process]

        monitor = ProcessMonitor("Telegram.exe", event_bus=MagicMock())

        assert monitor._find_process_id() == 1234

    def test_monitor_zero_cpu_when_process_alive(self, mock_psutil, mock_kernel32):
        """验证存活监控利用操作系统句柄等待而非轮询，确保零 CPU 开销。"""
        monitor = ProcessMonitor(
            "Telegram.exe",
            check_interval=0.5,
            event_bus=MagicMock()
        )

        monitor.last_PID = 1234

        # 验证底层 API 调用符合零轮询开销策略
        result = monitor._wait_for_process_change(last_status=True)

        mock_kernel32.OpenProcess.assert_called_once()
        mock_kernel32.WaitForSingleObject.assert_called_once()
        mock_kernel32.CloseHandle.assert_called_once()

        assert result is True

    @pytest.mark.asyncio
    async def test_monitor_start_already_running(self):
        """验证监控器不可重入，防止状态污染。"""
        monitor = ProcessMonitor("Telegram.exe", event_bus=MagicMock())

        await monitor.start_watching()

        try:
            with pytest.raises(RuntimeError, match="监视器已启动"):
                await monitor.start_watching()
        finally:
            await monitor.stop_watching()
