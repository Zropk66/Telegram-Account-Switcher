"""tg:// URL 多实例选择对话框."""

import threading
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class URLInstanceSelector(QDialog):
    """选择 Telegram 实例对话框."""

    def __init__(
        self,
        instances: List[Tuple[str, str, int]],
        url: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        """初始化."""
        super().__init__(parent)
        self.setWindowTitle("选择 Telegram 实例")
        self.setMinimumWidth(360)
        self._instances = instances
        self._selected_index: Optional[int] = None

        layout = QVBoxLayout(self)

        if url:
            label = QLabel(f'请在下方选择用于打开链接的客户端:\n{url}')
            label.setWordWrap(True)
            layout.addWidget(label)
        else:
            layout.addWidget(QLabel("请选择用于打开链接的客户端:"))

        self._list = QListWidget()
        for tag_name, target_folder, pid in instances:
            item_text = f"  {tag_name}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, target_folder)
            self._list.addItem(item)

        if instances:
            self._list.setCurrentRow(0)

        self._list.doubleClicked.connect(self._accept)
        layout.addWidget(self._list)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _accept(self) -> None:
        """确认选择."""
        row = self._list.currentRow()
        if row >= 0:
            self._selected_index = row
        self.accept()

    @property
    def selected_target_folder(self) -> Optional[str]:
        """获取选中的 target_folder."""
        if self._selected_index is None:
            return None
        item = self._list.item(self._selected_index)
        if item is None:
            return None
        return item.data(Qt.UserRole)

    @property
    def selected_tag(self) -> Optional[str]:
        """获取选中的标签名."""
        if self._selected_index is None:
            return None
        tag_name, _, _ = self._instances[self._selected_index]
        return tag_name


class URLSelectorBridge(QObject):
    """跨线程 URL 实例选择桥接器."""

    _show_signal = Signal(object, str)

    def __init__(self) -> None:
        """初始化桥接器."""
        super().__init__()
        self._result: Optional[str] = None
        self._event = threading.Event()
        self._show_signal.connect(self._on_show)

    @staticmethod
    def _run_dialog(instances: List[Tuple[str, str, int]], url: str) -> Optional[str]:
        """执行选择对话框，返回选中的 target_folder."""
        dialog = URLInstanceSelector(instances, url)
        if dialog.exec() == QDialog.Accepted:
            return dialog.selected_target_folder
        return None

    def _on_show(self, instances: object, url: str) -> None:
        """主线程槽函数：显示选择对话框."""
        self._result = self._run_dialog(instances, url)  # type: ignore[arg-type]
        self._event.set()

    def select(self, instances: List[Tuple[str, str, int]], url: str, timeout: float = 60.0) -> Optional[str]:
        """线程安全的实例选择，阻塞直到用户选择."""
        if threading.current_thread() == threading.main_thread():
            return self._run_dialog(instances, url)

        self._event.clear()
        self._result = None
        self._show_signal.emit(instances, url)
        self._event.wait(timeout=timeout)
        return self._result
