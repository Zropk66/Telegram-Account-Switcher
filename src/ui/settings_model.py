"""账户列表数据模型."""

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from src.ui.popup import alert


class AccountListModel:
    """账户列表界面数据模型."""

    def __init__(self, list_widget: QListWidget, current_configs: Dict[str, Any]) -> None:
        """初始化账户列表数据模型."""
        self.list_widget = list_widget
        self.current_configs = current_configs

    def load_from_config(self) -> None:
        """从临时配置对象中加载账户数据到列表中."""
        self.list_widget.clear()
        tags_data = self.current_configs.get("tags", {})
        if isinstance(tags_data, dict):
            for tag_name, account_data in tags_data.items():
                if isinstance(account_data, dict):
                    data = account_data.copy()
                    data["tag"] = tag_name
                    item = QListWidgetItem("")
                    item.setData(Qt.UserRole, data)
                    self.list_widget.addItem(item)
        self.refresh_display()

    def sync_to_config(self) -> None:
        """同步数据到临时配置对象."""
        new_tags = {}
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            data = item.data(Qt.UserRole)
            if data:
                tag_name = data.get("tag", "")
                account_data = {
                    "id": data.get("id", ""),
                    "folder": data.get("folder", ""),
                    "info": data.get("info", ""),
                    "identity": data.get("identity", ""),
                    "key": data.get("key", ""),
                }
                new_tags[tag_name] = account_data

        self.current_configs["tags"] = new_tags
        self.refresh_display()

    def add_account(self, data: Dict[str, Any]) -> None:
        """向列表中追加账户数据."""
        item = QListWidgetItem("")
        item.setData(Qt.UserRole, data)
        self.list_widget.addItem(item)
        self.sync_to_config()

    def remove_current(self) -> bool:
        """移除选定账户."""
        item = self.list_widget.currentItem()
        if not item:
            alert("未选择任何账号", "提示", "warning")
            return False

        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)
        self.sync_to_config()
        return True

    def update_item(self, item: QListWidgetItem, data: Dict[str, Any]) -> None:
        """更新列表中指定行的数据."""
        item.setData(Qt.UserRole, data)
        self.sync_to_config()

    def refresh_display(self, default_tag: Optional[str] = None) -> None:
        """刷新列表中各账户行的文本显示."""
        if not default_tag:
            default_tag = self.current_configs.get("default", "")
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            data = item.data(Qt.UserRole)
            if data:
                tag = data.get("tag", "")
                id_val = str(data.get("id", ""))
                display_text = tag if tag else id_val
                if (tag and tag == default_tag) or (not tag and id_val == default_tag):
                    display_text += " [默认]"
                item.setText(display_text)
