# -*- coding: utf-8 -*-
from typing import Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QListWidget

from src.modules import ConfigManage


class AccountListModel:
    """管理账号列表的数据表示层"""

    def __init__(self, list_widget: QListWidget, config: ConfigManage):
        self.list_widget = list_widget
        self.config = config

    def load_from_config(self):
        """从配置加载账户到列表"""
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
        """从列表同步数据到配置"""
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
        """添加单个账户"""
        item = QListWidgetItem("")
        item.setData(Qt.UserRole, data)
        self.list_widget.addItem(item)
        self.sync_to_config()

    def remove_current(self, sync_callback=None):
        """删除当前选中账户"""
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
        """更新列表项数据"""
        item.setData(Qt.UserRole, data)
        self.sync_to_config()

    def refresh_display(self, default_tag: str = None):
        """刷新列表项的显示文本"""
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
