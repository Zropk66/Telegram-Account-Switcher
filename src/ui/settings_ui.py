# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import os
import sys
from contextlib import suppress
from pathlib import Path
from threading import RLock

from PySide6.QtCore import Qt, QThreadPool, Slot, QPoint
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QFileDialog, QApplication, QMenu, QDialog

from src.modules import TASConfigException, Logger, ConfigManage
from src.ui.dialogs import EditLabelDialog, SettingsDialogHelper
from src.ui.settings_model import AccountListModel
from src.ui.ui_controller import alert, confirm
from src.ui.ui_settings import Ui_setting
from src.ui.ui_utils import (
    DoubleClickFilter,
    AccountScannerHelper, AsyncTaskRunner, DialogFactory
)


def open_settings_window(version):
    app = QApplication.instance() or QApplication(sys.argv)
    widget = SettingsWindow(version)
    app._settings_window = widget
    widget.show()
    return app.exec()


class SettingsController:
    """中介者：处理 UI 事件背后的业务逻辑"""

    def __init__(self, window: 'SettingsWindow'):
        self.window = window
        self.config = ConfigManage()
        self.model = AccountListModel(window.ui.tags_widget, self.config)
        self.thread_pool = QThreadPool.globalInstance()

    def search_client_async(self):
        """异步搜索客户端"""
        AsyncTaskRunner.run_search_client(
            self.thread_pool,
            self._on_search_client_finished,
            self._on_error
        )

    def _on_search_client_finished(self, result):
        client, path = result
        self.window.ui.client_edit.setText(client)
        self.window.ui.path_edit.setText(path)
        self.window.update_current_config('client', client)
        self.window.update_current_config('path', path)
        Logger().info(f"有效客户端 -> {Path(path) / client}")

    def _on_error(self, e):
        Logger().error(e.message, popup=True)

    def scan_accounts(self, base_path: str):
        """扫描账户"""
        if not base_path or not Path(base_path).exists():
            alert("请输入有效的 Telegram 客户端路径", "警告", "warning")
            return

        if not self.window.current_configs.get("agreed_to_decrypt", False):
            if not confirm("这是您第一次使用寻找多账号功能。\n使用该功能需要解密该目录下的本地账户数据，您同意继续吗？",
                           "解密确认"):
                return
            self.window.update_current_config("agreed_to_decrypt", True)

        existing_folders = AccountScannerHelper.get_existing_folders(self.window.ui.tags_widget)

        passcode = self.config.pwd
        accounts = self.config.scan_accounts_from_path(base_path, passcode)

        if not accounts:
            alert("未找到任何账户", "提示")
            return

        added_count = 0
        for folder_name, account_data in accounts.items():
            if folder_name in existing_folders:
                continue

            data = account_data.copy()
            AccountScannerHelper.write_tag_file(base_path, folder_name, data.get('tag', folder_name))

            self.model.add_account(data)
            added_count += 1

        alert(f"已发现 {len(accounts)} 个账户，新增 {added_count} 个", "成功")
        return accounts


class SettingsWindow(QMainWindow):
    def __init__(self, version):
        super().__init__()
        self.ui = Ui_setting()
        self.ui.setupUi(self)
        self.controller = SettingsController(self)
        self.config_manage = ConfigManage()
        self.current_configs = self.config_manage.configs
        self.lock = RLock()

        self.ui.version_label.setText(f'TAS v{version}')

        # 客户端设置
        self.client_edit_double_click_filter = DoubleClickFilter(self.select_client_event)
        self.ui.client_edit.installEventFilter(self.client_edit_double_click_filter)
        self.ui.client_edit.setText(self.current_configs.get('client'))

        # 路径设置
        self.path_edit_double_click_filter = DoubleClickFilter(self.select_path_event)
        self.ui.path_edit.installEventFilter(self.path_edit_double_click_filter)
        self.ui.path_edit.setText(self.current_configs.get('path'))

        # 账号列表加载
        self.controller.model.load_from_config()
        self.ui.tags_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.log_output.setChecked(self.current_configs.get('log_output'))

        self._connect_signals()

    def _connect_signals(self):
        self.ui.client_edit.textChanged.connect(lambda t: self.update_current_config('client', t))
        self.ui.path_edit.textChanged.connect(lambda t: self.update_current_config('path', t))
        self.ui.search_client_button.clicked.connect(self.controller.search_client_async)
        self.ui.tags_widget.itemDoubleClicked.connect(self.edit_item_event)
        self.ui.search_account_button.clicked.connect(self.scan_account_event)
        self.ui.del_button.clicked.connect(self.remove_item_event)
        self.ui.tags_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.ui.log_output.stateChanged.connect(lambda s: self.update_current_config('log_output', bool(s)))
        self.ui.finish_button.clicked.connect(self.save_config_event)
        with suppress(AttributeError):
            self.ui.cancel_button.clicked.connect(self.close)

    def closeEvent(self, event: QCloseEvent) -> None:
        if ConfigManage().configs != self.current_configs:
            if confirm("配置已更改但未保存，你确定要退出程序吗？", "Tips"):
                event.accept()
            else:
                event.ignore()

    def show_context_menu(self, pos: QPoint):
        item = self.ui.tags_widget.itemAt(pos)
        menu = QMenu()
        add_action = menu.addAction("添加账户")
        delete_action = menu.addAction("删除账户") if item else None

        action = menu.exec(self.ui.tags_widget.mapToGlobal(pos))
        if action == add_action:
            self.add_item_event()
        elif delete_action and action == delete_action:
            self.controller.model.remove_current(
                lambda: self.update_current_config('tags', self.config_manage.get_all_accounts())
            )

    def update_current_config(self, key, value):
        self.current_configs[key] = value

    @Slot()
    def save_config_event(self):
        try:
            ConfigManage().batch_update(self.current_configs)
            Logger().info('配置保存成功')
            alert('配置已保存', '成功')
        except TASConfigException as e:
            Logger().exception("配置保存失败", e)

    @Slot()
    def add_item_event(self):
        dialog = EditLabelDialog("", "", "", "", "", "", self)
        if dialog.exec() == QDialog.Accepted:
            self._handle_edit_dialog_result(None, dialog)

    @Slot()
    def edit_item_event(self, item):
        data = item.data(Qt.UserRole)
        dialog = EditLabelDialog(
            data.get('id', ''), data.get('folder', ''), data.get('tag', ''),
            data.get('info', ''), data.get('identity', ''), data.get('key', ''), self
        )
        if dialog.exec() == QDialog.Accepted:
            self._handle_edit_dialog_result(item, dialog)

    @Slot()
    def scan_account_event(self):
        self.controller.scan_accounts(self.ui.path_edit.text())
        self.current_configs['tags'] = self.config_manage.get_all_accounts()

    def _handle_edit_dialog_result(self, item, dialog):
        """处理编辑对话框的结果"""
        SettingsDialogHelper.handle_edit_dialog_result(
            item,
            dialog,
            self.current_configs,
            self.ui.path_edit.text(),
            self.update_current_config,
            self.controller.model.update_item,
            self.controller.model.add_account,
            self.config_manage,
            self.controller.model.refresh_display
        )

    @Slot()
    def remove_item_event(self):
        self.controller.model.remove_current(
            lambda: self.update_current_config('tags', self.config_manage.get_all_accounts())
        )

    @Slot()
    def select_client_event(self):
        user_select, _ = QFileDialog.getOpenFileName(self, "选择客户端", "", "客户端主程序 (*.exe)")
        if user_select:
            client, path = os.path.basename(user_select), os.path.dirname(user_select)
            self.ui.client_edit.setText(client)
            self.ui.path_edit.setText(path)
            self.update_current_config('client', client)
            self.update_current_config('path', path)

    @Slot()
    def select_path_event(self):
        user_select = DialogFactory.browse_folder(self, "选择路径")
        if user_select:
            self.ui.path_edit.setText(user_select)
            self.update_current_config('path', user_select)


__all__ = ['SettingsWindow', 'open_settings_window', 'alert', 'confirm']

alert = alert
confirm = confirm
