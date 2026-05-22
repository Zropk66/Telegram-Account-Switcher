"""进程管理单元测试。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core import ProcessInfo
from src.core.exceptions import TASException
from src.core.process_manager import ProcessManager


class TestProcessManager:
    """
    针对 ProcessManager 进程生命周期管理功能的单元测试套件。
    """

    def test_start_process_wait_for_ready(self, mock_config):
        """验证启动 Telegram 进程并同步等待就绪状态。"""
        pm = ProcessManager(config=mock_config)

        with patch.object(Path, 'exists', return_value=True):
            mock_popen = MagicMock()
            with patch('subprocess.Popen', return_value=mock_popen) as mock_popen_call:
                with patch.object(pm._process_service, 'find_processes', side_effect=[
                    [],
                    [ProcessInfo(pid=1234, name="Telegram.exe")]
                ]) as mock_find:
                    result = pm.start_process(wait=True)

                    assert result is True
                    mock_popen_call.assert_called_once()
                    assert mock_find.call_count == 2

    def test_start_process_not_found(self, mock_config):
        """验证目标可执行文件路径不存在时，正确拒绝启动。"""
        pm = ProcessManager(config=mock_config)

        with patch.object(Path, 'exists', return_value=False):
            result = pm.start_process(wait=False)
            assert result is False

    def test_kill_process_terminate_then_kill(self):
        """验证清理进程时，优先尝试优雅终止，超时后强制清理。"""
        from src.core.process_service import MockProcessService
        mock_service = MockProcessService()
        pm = ProcessManager(process_service=mock_service)

        p1 = mock_service.add_process('Telegram.exe', pid=101)
        p2 = mock_service.add_process('Telegram.exe', pid=102)

        with patch.object(mock_service, 'terminate', side_effect=[True, False]) as mock_term:
            with patch.object(mock_service, 'kill', return_value=True) as mock_kill:
                from src.core import ProcessInfo
                with patch.object(mock_service, 'find_processes', side_effect=[
                    [ProcessInfo(101, 'Telegram.exe'), ProcessInfo(102, 'Telegram.exe')],
                    [ProcessInfo(102, 'Telegram.exe')],
                    []
                ]):
                    result = pm.kill_process('Telegram.exe')

                    assert result is True
                    assert mock_term.call_count == 2
                    mock_kill.assert_called_once_with(102)

    def test_kill_process_access_denied(self):
        """验证因权限不足导致清理失败时，抛出预期异常。"""
        from src.core.process_service import MockProcessService

        mock_service = MockProcessService()
        pm = ProcessManager(process_service=mock_service)

        mock_proc = mock_service.add_process('Telegram.exe', pid=123)

        with patch.object(mock_service, 'terminate', return_value=False):
            with patch.object(mock_service, 'kill', return_value=False):
                with pytest.raises(TASException) as exc_info:
                    pm.kill_process('Telegram.exe')

                assert "权限不足" in str(exc_info.value)

    def test_locked_context_kills_on_enter(self):
        """验证在保护上下文中，进入时自动终止旧实例，退出时重启。"""
        pm = ProcessManager()

        with patch.object(pm, 'kill_process') as mock_kill:
            with patch.object(pm, 'start_process') as mock_start:
                with pm.kill_and_guard('Telegram.exe', restart_on_exit=True):
                    mock_kill.assert_called_once_with('Telegram.exe')
                    mock_start.assert_not_called()

                mock_start.assert_called_once_with(wait=False)

