"""界面工具与辅助函数。"""

from pathlib import Path
from typing import Set, Optional

from PySide6.QtCore import QRegularExpression, Qt, QObject, QEvent
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QStyledItemDelegate, QLineEdit, QListWidget

from src.core.constants import TAG_FILE


class NonEmptyDelegate(QStyledItemDelegate):
    """约束输入内容必须为非空字符的编辑框委托。"""

    def createEditor(self, parent, option, index):
        """创建行编辑器并设置正则校验。"""
        editor = QLineEdit(parent)
        regex = QRegularExpression(r"^[^\\s](.*[^\\s])?$")
        validator = QRegularExpressionValidator(regex, editor)
        editor.setValidator(validator)
        return editor


class DoubleClickFilter(QObject):
    """拦截双击事件并触发回调。"""

    def __init__(self, callback, target_widget=None):
        """初始化双击过滤器。"""
        super().__init__()
        self.callback = callback
        self.target_widget = target_widget

    def eventFilter(self, obj, event):
        """过滤和捕获指定控件的双击事件。"""
        if event.type() == QEvent.MouseButtonDblClick:
            if event.button() == Qt.LeftButton:
                if self.target_widget is None or obj is self.target_widget:
                    self.callback()
                    return True
        return super().eventFilter(obj, event)


class AccountScannerHelper:
    """账户扫描辅助类。"""

    @staticmethod
    def validate_path(base_path: str) -> bool:
        """验证基础路径是否合法且存在。"""
        if not base_path or not Path(base_path).exists():
            from src.ui.popup import alert
            alert("请输入有效的 Telegram 客户端路径", "警告", "warning")
            return False
        return True

    @staticmethod
    def get_existing_folders(list_widget: QListWidget) -> Set[str]:
        """获取界面中已添加的账户文件夹集合。"""
        existing_folders = set()
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            data = item.data(Qt.UserRole)
            if data and data.get('folder'):
                existing_folders.add(data.get('folder'))
        return existing_folders

    @staticmethod
    def write_tag_file(base_path: str, folder_name: str, tag_name: str) -> bool:
        """写入标签名称至目标文件夹的标签文件中。"""
        try:
            tag_file = Path(base_path) / folder_name / TAG_FILE
            tag_file.write_text(tag_name, encoding="utf-8")
            return True
        except Exception as e:
            from src.core.logger import Logger
            Logger().error(f"写入 {TAG_FILE} 标签文件失败: {e}")
            return False


class BackgroundTaskRunner:
    """后台任务运行辅助类。"""

    @staticmethod
    def run_search_client(thread_pool, finished_callback, error_callback):
        """在后台线程执行 Telegram 客户端搜索。"""
        from src.ui.settings_services import TaskRunner
        from src.core.env_service import TelegramEnvService

        def task():
            """执行客户端路径搜索。"""
            return TelegramEnvService.search_client()

        runner = TaskRunner(task)
        runner.signals.finished.connect(finished_callback)
        runner.signals.error.connect(error_callback)
        thread_pool.start(runner)


class DialogFactory:
    """弹窗及对话框生成工厂。"""

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
        """创建账户标签编辑对话框。"""
        from src.ui.dialogs import EditLabelDialog
        return EditLabelDialog(user_id, folder, tag, info, identity, key, parent)

    @staticmethod
    def create_show_key_dialog(
        info: str = "",
        identity: str = "",
        key: str = "",
        parent=None
    ):
        """创建账户密钥查看对话框。"""
        from src.ui.dialogs import ShowKeyDialog
        return ShowKeyDialog(info, identity, key, parent)

    @staticmethod
    def browse_folder(parent=None, caption: str = "选择文件夹") -> Optional[str]:
        """弹出系统选择文件夹对话框。"""
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(parent, caption)
        return folder if folder else None

    @staticmethod
    def browse_file(parent=None, caption: str = "选择文件", filter: str = "所有文件 (*.*)") -> Optional[str]:
        """弹出系统选择文件对话框。"""
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(parent, caption, "", filter)
        return file_path if file_path else None
