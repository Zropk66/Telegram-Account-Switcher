# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import asyncio
import json
import os
import time

from PySide6.QtCore import QObject, QEvent, Qt, QRunnable, QThreadPool, QProcess, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMainWindow, QMessageBox, QFileDialog, QListWidgetItem

from src.ui.ui_settings import Ui_setting
from src.utils.files_utils import config_helper
from src.utils.logger import logger
from src.utils.process_utils import get_process_path, async_check_process_is_run
from utils.files_utils import config_manager
from utils.process_utils import try_kill_process, try_find_client


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_setting()
        self.ui.setupUi(self)
        self.threadPool = QThreadPool.globalInstance()

        self.get_client_lock = False
        self.get_path_lock = False

        try:
            self.config = config_manager()
            self.client = self.config.get("client")
            if self.client is None or self.client == '':
                self.client = 'Telegram.exe'

            path = self.config.get("path")
            default = self.config.get("default")
            tags = self.config.get("tags")
        except Exception:
            logger.error('获取默认配置时出现错误.', exc_info=True)
            self.client = path = default = tags = ''

        self.ui.client_edit.setText(self.client)
        self.ui.path_edit.setText(path)
        self.ui.default_edit.setText(default)
        self.ui.tags_widget.addItems(tags)

        for i in range(self.ui.tags_widget.count()):
            item = self.ui.tags_widget.item(i)
            item.setFlags(item.flags() | Qt.ItemIsEditable)

        self.client_edit_double_click_filter = self.DoubleClickFilter(self.client_edit_double_click_event)
        self.ui.client_edit.installEventFilter(self.client_edit_double_click_filter)
        self.ui.client_button.clicked.connect(lambda: self.threadPool.start(self.Worker(self.get_client)))

        self.path_edit_double_click_filter = self.DoubleClickFilter(self.path_edit_double_click_event)
        self.ui.path_edit.installEventFilter(self.path_edit_double_click_filter)
        self.ui.path_button.clicked.connect(lambda: self.threadPool.start(self.Worker(self.get_path)))

        self.ui.add_button.clicked.connect(self.add_item)
        self.ui.del_button.clicked.connect(self.del_item)
        self.ui.tags_widget.itemDoubleClicked.connect(self.edit_item)

        self.ui.finish_button.clicked.connect(self.finish)

    class Worker(QRunnable):
        def __init__(self, fun):
            super().__init__()
            self.fun = fun

        def run(self):
            self.fun()

    def get_path(self):
        """自动获取路径"""
        if self.get_path_lock:
            return
        self.get_path_lock = True
        if not self.client:
            logger.warning('客户端名称未设置，请先获取客户端名称后重试.')
        try:
            QDesktopServices.openUrl(QUrl("tg:"))
        except Exception as e:
            logger.error(e)
        client_is_run = asyncio.run(async_check_process_is_run(str(self.client), 10, 1))
        if not client_is_run:
            logger.warning("无法获取到路径，您使用的telegram可能不在我们的预设池里，请手动设置.")
            return
        effective_path = get_process_path(str(self.client))
        if not (isinstance(effective_path, str) and os.path.isfile(
                os.path.join(str(effective_path), str(self.client)))):
            raise ValueError(f"无效路径: {effective_path}")
        try_kill_process(str(self.client))
        logger.info(f"有效路径 -> {effective_path}")
        self.config.set('path', effective_path)
        self.ui.path_edit.setText(effective_path)
        self.get_path_lock = False
        return

    def get_client(self):
        """自动获取客户端"""
        if self.get_client_lock:
            return
        self.get_client_lock = True

        process = QProcess(self)
        QDesktopServices.openUrl(QUrl("tg:"))

        client_map = [
            'iMe',
            'telegram',
            'Forkgram',
            '64Gram',
            'Unigram',
            'Beeper',
            'AyuGram'
        ]
        client = None

        for _ in range(10):
            if process.waitForFinished(1000):
                break
            client = try_find_client(client_map)
            if client: break

        if not client is None:
            logger.info(f"有效客户端 -> {client}")
            config_helper(field='client', mode='w', value=client)
            self.ui.client_edit.setText(str(client))
            self.client = client
        else:
            logger.warning('无效客户端.')
            self.ui.client_edit.setText('')
        time.sleep(1)
        try_kill_process(self.client)
        self.get_client_lock = False

    def finish(self):
        """保存所有设置"""
        config = {
            'client': self.ui.client_edit.text(),
            'path': self.ui.path_edit.text(),
            'default': self.ui.default_edit.text(),
            'tags': [self.ui.tags_widget.item(i).text() for i in range(self.ui.tags_widget.count())]
        }
        json.dumps(config, indent=4)
        self.config.save_multiple_fields(config)
        QMessageBox.information(None, '提示', '设置保存成功.')

    def add_item(self):
        item = QListWidgetItem("New argument")
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.ui.tags_widget.addItem(item)
        self.ui.tags_widget.editItem(item)

    def del_item(self):
        selected_item = self.ui.tags_widget.currentItem()
        if selected_item:
            row = self.ui.tags_widget.row(selected_item)
            self.ui.tags_widget.takeItem(row)

    def edit_item(self, item):
        """当用户双击某个项时，进入编辑模式"""
        self.ui.tags_widget.editItem(item)

    def client_edit_double_click_event(self):
        """客户端选择事件"""
        userSelect, _ = QFileDialog.getOpenFileName(self, "选择客户端", "", "客户端主程序 (*.exe)")
        if userSelect:
            client = os.path.basename(userSelect)
            path = os.path.dirname(userSelect)
            self.ui.client_edit.setText(client)
            self.ui.path_edit.setText(path)

    def path_edit_double_click_event(self):
        """路径选择事件"""
        path = QFileDialog.getExistingDirectory(self, "选择客户端路径", "")
        if path:
            self.ui.path_edit.setText(path)

    class DoubleClickFilter(QObject):
        def __init__(self, fun):
            super().__init__()
            self.fun = fun

        def eventFilter(self, obj, event):
            if event.type() == QEvent.MouseButtonDblClick:
                self.fun()
                return True
            return super().eventFilter(obj, event)
