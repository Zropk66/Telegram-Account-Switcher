"""
UI 工具类集合，包含界面编辑委托、事件过滤、账户辅助与工厂类。
"""

from pathlib import Path
from typing import Set, Optional

from PySide6.QtCore import QRegularExpression, Qt, QObject, QEvent
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QStyledItemDelegate, QLineEdit, QListWidget


class NonEmptyDelegate(QStyledItemDelegate):
    """防止在列表编辑中输入空白字符串的委托类。"""

    def createEditor(self, parent, option, index):
        """应用正则约束，要求非空字符输入。"""
        editor = QLineEdit(parent)
        regex = QRegularExpression(r"^[^\\s](.*[^\\s])?$")
        validator = QRegularExpressionValidator(regex, editor)
        editor.setValidator(validator)
        return editor


class DoubleClickFilter(QObject):
    """用于在控件上捕获双击事件并执行回调的过滤器。"""

    def __init__(self, callback, target_widget=None):
        """初始化。"""
        super().__init__()
        self.callback = callback
        self.target_widget = target_widget

    def eventFilter(self, obj, event):
        """截获鼠标双击，确保在特定目标上触发回调。"""
        if event.type() == QEvent.MouseButtonDblClick:
            if event.button() == Qt.LeftButton:
                if self.target_widget is None or obj is self.target_widget:
                    self.callback()
                    return True
        return super().eventFilter(obj, event)


class AccountScannerHelper:
    """账户导入扫描辅助类，负责路径合法性检查及标记文件处理。"""

    @staticmethod
    def validate_path(base_path: str) -> bool:
        """检查路径是否存在并提示。"""
        if not base_path or not Path(base_path).exists():
            from src.ui.popup import alert
            alert("请输入有效的 Telegram 客户端路径", "警告", "warning")
            return False
        return True

    @staticmethod
    def get_existing_folders(list_widget: QListWidget) -> Set[str]:
        """从当前 UI 列表中提取已添加的账户文件夹集合，用于扫描去重。"""
        existing_folders = set()
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            data = item.data(Qt.UserRole)
            if data and data.get('folder'):
                existing_folders.add(data.get('folder'))
        return existing_folders

    @staticmethod
    def write_tag_file(base_path: str, folder_name: str, tag_name: str) -> bool:
        """在账户目录下写入 `tas_tag` 文件以关联标识。"""
        try:
            tag_file = Path(base_path) / folder_name / "tas_tag"
            tag_file.write_text(tag_name, encoding="utf-8")
            return True
        except Exception:
            return False


class AsyncTaskRunner:
    """提供将同步任务卸载至后台线程池的调度接口。"""

    @staticmethod
    def run_search_client(thread_pool, finished_callback, error_callback):
        """异步执行环境搜索任务，并通过信号回调。"""
        from src.ui.settings_services import TaskRunner
        from src.core.env_service import TelegramEnvService

        def task():
            """task 方法。"""
            return TelegramEnvService.search_client()

        runner = TaskRunner(task)
        runner.signals.finished.connect(finished_callback)
        runner.signals.error.connect(error_callback)
        thread_pool.start(runner)


class DialogFactory:
    """集中创建常用弹窗对话框的工厂类。"""

    @staticmethod
    def create_edit_label_dialog(
        user_id: str = "",
        folder: str = "",
        tag: str = "",
        info: str = "",
        identity: str = "",
        key: str = "",
        parent=None
    ):
        """构造账户信息编辑框。"""
        from src.ui.dialogs import EditLabelDialog
        return EditLabelDialog(user_id, folder, tag, info, identity, key, parent)

    @staticmethod
    def create_show_key_dialog(
        info: str = "",
        identity: str = "",
        key: str = "",
        parent=None
    ):
        """构造加密密钥显示框。"""
        from src.ui.dialogs import ShowKeyDialog
        return ShowKeyDialog(info, identity, key, parent)

    @staticmethod
    def browse_folder(parent=None, caption: str = "选择文件夹") -> Optional[str]:
        """调用文件系统浏览目录。"""
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(parent, caption)
        return folder if folder else None

    @staticmethod
    def browse_file(parent=None, caption: str = "选择文件", filter: str = "所有文件 (*.*)") -> Optional[str]:
        """调用文件系统浏览特定文件。"""
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(parent, caption, "", filter)
        return file_path if file_path else None
