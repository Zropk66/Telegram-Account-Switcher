# -*- coding: utf-8 -*-
import os
import winreg
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QRunnable, Slot

from src.modules import TASException


class SystemScannerService:
    """系统扫描服务：处理注册表查询和文件路径提取"""

    @staticmethod
    def search_client() -> tuple[str, str]:
        """从注册表自动查找客户端程序和路径"""
        try:
            protocol_key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"tg", 0, winreg.KEY_READ)
            with winreg.OpenKey(protocol_key, r"shell\open\command") as command_key:
                command = winreg.QueryValue(command_key, None)
                full_path = Path(SystemScannerService.extract_executable_path(command)).resolve(strict=True)
                if not full_path or not os.path.exists(full_path):
                    raise TASException('提取的客户端路径无效或文件不存在.')

                client = os.path.basename(full_path)
                path = os.path.dirname(full_path)
                return client, path
        except (FileNotFoundError, AttributeError) as e:
            raise TASException('无法找到客户端，请确保协议关联已安装并注册') from e
        except RuntimeError as e:
            raise TASException(f'注册表操作失败') from e
        except PermissionError as e:
            raise TASException('如果权限不足，请以管理员身份运行该程序') from e
        except OSError as e:
            raise TASException(f'系统错误({e.winerror}): {e.strerror}') from e

    @staticmethod
    def extract_executable_path(command: str) -> str:
        """解析命令行中的执行文件路径"""
        if not command:
            raise AttributeError("命令字符串为空")

        try:
            if command.startswith('"'):
                end_quote = command.find('"', 1)
                if end_quote != -1:
                    return command[1:end_quote]

            parts = command.split()
            if parts:
                candidate = parts[0]
                if os.path.exists(candidate):
                    return candidate

                clean_candidate = candidate.strip('"\'')
                if os.path.exists(clean_candidate):
                    return clean_candidate
                return candidate
            return command
        except AttributeError:
            raise

class SignalsEmitter(QObject):
    """通用的信号发射器"""
    finished = Signal(object)
    warning = Signal(object)
    error = Signal(object)
    exception = Signal(Exception)
    signal = Signal(object)

class TaskRunner(QRunnable):
    """异步任务执行器"""
    def __init__(self, func):
        super().__init__()
        self.func = func
        self.signals = SignalsEmitter()

    @Slot()
    def run(self):
        try:
            result = self.func()
            self.signals.finished.emit(result)
        except TASException as e:
            self.signals.error.emit(e)
        except Exception as e:
            self.signals.exception.emit(e)
