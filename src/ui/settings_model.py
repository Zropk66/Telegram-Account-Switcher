from typing import Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QListWidget

from src.core.config import ConfigService


class AccountListModel:
    """账户列表的数据层，负责列表项的增删改查以及和 ConfigService 的同步。"""

    def __init__(self, list_widget: QListWidget, config: ConfigService):
        self.list_widget = list_widget
        self.config = config

    def load_from_config(self):
        """从配置中读取所有账户，填充到列表控件。"""
        self.list_widget.clear()
        tags_data = self.config.get_all_accounts()
        for tag_name, account_data in tags_data.items():
            data = account_data.copy()
            data['tag'] = tag_name
            item = QListWidgetItem("")
            item.setData(Qt.UserRole, data)
            self.list_widget.addItem(item)
        self.refresh_display()

    def sync_to_config(self):
        """把列表里的数据写回配置，保持两边一致。"""
        new_tags = {}
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            data = item.data(Qt.UserRole)
            if data:
                tag_name = data.get('tag', '')
                account_data = {
                    'id': data.get('id', ''),
                    'folder': data.get('folder', ''),
                    'info': data.get('info', ''),
                    'identity': data.get('identity', ''),
                    'key': data.get('key', '')
                }
                new_tags[tag_name] = account_data

        self.config.tags = new_tags
        self.refresh_display()

    def add_account(self, data: Dict[str, Any]):
        """往列表末尾追加一个账户。"""
        item = QListWidgetItem("")
        item.setData(Qt.UserRole, data)
        self.list_widget.addItem(item)
        self.sync_to_config()

    def remove_current(self, sync_callback=None):
        """删除当前选中的账户，返回是否成功。"""
        item = self.list_widget.currentItem()
        if item:
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)
            self.sync_to_config()
            if sync_callback:
                sync_callback()
            return True
        return False

    def update_item(self, item: QListWidgetItem, data: Dict[str, Any]):
        """用新数据替换某个列表项的内容。"""
        item.setData(Qt.UserRole, data)
        self.sync_to_config()

    def refresh_display(self, default_tag: str = None):
        """根据数据重新渲染每行的显示文本，默认账户会标注 [默认]。"""
        if not default_tag:
            default_tag = self.config.default
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            data = item.data(Qt.UserRole)
            if data:
                tag = data.get('tag', '')
                id_val = str(data.get('id', ''))
                display_text = tag if tag else id_val
                if (tag and tag == default_tag) or (not tag and id_val == default_tag):
                    display_text += " [默认]"
                item.setText(display_text)
