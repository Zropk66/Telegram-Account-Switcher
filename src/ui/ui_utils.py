from pathlib import Path
from typing import Set, Optional

from PySide6.QtCore import QRegularExpression, Qt, QObject, QEvent
from PySide6.QtGui import QRegularExpressionValidator, QValidator
from PySide6.QtWidgets import QStyledItemDelegate, QLineEdit, QListWidget


class NonEmptyDelegate(QStyledItemDelegate):
    """列表项编辑委托，不允许输入纯空白。"""

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        regex = QRegularExpression(r"^[^\s](.*[^\s])?$")
        validator = QRegularExpressionValidator(regex, editor)
        editor.setValidator(validator)
        return editor


class NonEmptyValidator(QValidator):
    """简单的非空验证器，空白字符会被忽略。"""

    def validate(self, input_str, pos):
        input_str = input_str.replace(' ', '')
        return QValidator.Acceptable, input_str, pos


class DoubleClickFilter(QObject):
    """双击事件过滤器，安装到输入框上可以响应双击打开选择器。"""

    def __init__(self, callback, target_widget=None):
        super().__init__()
        self.callback = callback
        self.target_widget = target_widget

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonDblClick:
            if event.button() == Qt.LeftButton:
                if self.target_widget is None or obj is self.target_widget:
                    self.callback()
                    return True
        return super().eventFilter(obj, event)


class AccountScannerHelper:
    """账户扫描时用到的一些静态工具方法。"""

    @staticmethod
    def validate_path(base_path: str) -> bool:
        if not base_path or not Path(base_path).exists():
            from src.ui.popup import alert
            alert("请输入有效的 Telegram 客户端路径", "警告", "warning")
            return False
        return True

    @staticmethod
    def get_existing_folders(list_widget: QListWidget) -> Set[str]:
        """收集列表中已有账户的文件夹名，扫描时用来去重。"""
        existing_folders = set()
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            data = item.data(Qt.UserRole)
            if data and data.get('folder'):
                existing_folders.add(data.get('folder'))
        return existing_folders

    @staticmethod
    def write_tag_file(base_path: str, folder_name: str, tag_name: str) -> bool:
        """在账户文件夹下写入 tas_tag 文件，标记该账户的标签。"""
        try:
            tag_file = Path(base_path) / folder_name / "tas_tag"
            tag_file.write_text(tag_name, encoding="utf-8")
            return True
        except Exception:
            return False


class AsyncTaskRunner:
    """把耗时操作丢到 QThreadPool 里跑，完成后通过回调通知 UI。"""

    @staticmethod
    def run_search_client(thread_pool, finished_callback, error_callback):
        from src.ui.settings_services import TaskRunner
        from src.core.env_service import TelegramEnvService

        def task():
            return TelegramEnvService.search_client()

        runner = TaskRunner(task)
        runner.signals.finished.connect(finished_callback)
        runner.signals.error.connect(error_callback)
        thread_pool.start(runner)


class DialogFactory:
    """集中创建各种对话框，避免在 UI 代码里到处 import。"""

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
        from src.ui.dialogs import EditLabelDialog
        return EditLabelDialog(user_id, folder, tag, info, identity, key, parent)

    @staticmethod
    def create_show_key_dialog(
        info: str = "",
        identity: str = "",
        key: str = "",
        parent=None
    ):
        from src.ui.dialogs import ShowKeyDialog
        return ShowKeyDialog(info, identity, key, parent)

    @staticmethod
    def browse_folder(parent=None, caption: str = "选择文件夹") -> Optional[str]:
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(parent, caption)
        return folder if folder else None

    @staticmethod
    def browse_file(parent=None, caption: str = "选择文件", filter: str = "所有文件 (*.*)") -> Optional[str]:
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(parent, caption, "", filter)
        return file_path if file_path else None
