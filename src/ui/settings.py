import json
import os
import subprocess
import time
import traceback

from PySide6.QtCore import QObject, QEvent, Qt, QRunnable, QThreadPool
from PySide6.QtWidgets import QMainWindow, QMessageBox, QFileDialog, QListWidgetItem

from src.ui.ui_settings import Ui_setting
from src.utils.process_utils import handle_process
from src.utils.files_utils import config_helper
from src.utils.logger import logger


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_setting()
        self.ui.setupUi(self)
        self.threadPool = QThreadPool.globalInstance()

        try:
            self.client = config_helper(field='client', mode='r')
            if self.client is None or self.client == '':
                self.client = 'Telegram.exe'
            path = config_helper(field='path', mode='r')
            default = config_helper(field='default', mode='r')
            args = config_helper(field='args', mode='r')
        except Exception:
            logger.error('获取默认配置时出现错误.')
            self.client = path = default = args = ''

        self.ui.clientEdit.setText(self.client)
        self.ui.pathEdit.setText(path)
        self.ui.defaultTdataEdit.setText(default)
        self.ui.argsWidget.addItems(args)

        for i in range(self.ui.argsWidget.count()):
            item = self.ui.argsWidget.item(i)
            item.setFlags(item.flags() | Qt.ItemIsEditable)

        self.client_edit_double_click_filter = self.DoubleClickFilter(self.client_edit_double_click_event)
        self.ui.clientEdit.installEventFilter(self.client_edit_double_click_filter)
        self.ui.clientbtn.clicked.connect(self.get_client)

        self.path_edit_double_click_filter = self.DoubleClickFilter(self.path_edit_double_click_event)
        self.ui.pathEdit.installEventFilter(self.path_edit_double_click_filter)
        self.ui.pathBtn.clicked.connect(self.get_path)

        self.ui.addBtn.clicked.connect(self.add_item)
        self.ui.delBtn.clicked.connect(self.del_item)
        self.ui.argsWidget.itemDoubleClicked.connect(self.edit_item)

        self.ui.finishBtn.clicked.connect(self.finish)

    class Worker(QRunnable):
        def __init__(self, fun):
            super().__init__()
            self.fun = fun

        def run(self):
            self.fun()

    def get_path(self):
        worker = self.Worker(self.path_auto_get)
        self.threadPool.start(worker)

    def get_client(self):
        worker = self.Worker(self.client_auto_get)
        self.threadPool.start(worker)

    def path_auto_get(self):
        """自动获取路径"""
        if self.client is None or self.client == '':
            logger.warning('客户端名称未设置，请先获取客户端名称后重试.')
        try:
            subprocess.Popen('start "" "tg:"', shell=True)
        except Exception as e:
            logger.error(e)
        client_is_run = False
        for i in range(10):
            if handle_process(client=self.client, mode='isRun'):
                client_is_run = True
                break
            time.sleep(1)
        if not client_is_run:
            logger.warning("无法获取到路径，您使用的telegram可能不在我们的预设池里，请手动设置.")
            return ''
        effective_path = ''
        for i in range(5):
            try:
                effective_path = handle_process(client=self.client, mode='path')
                if isinstance(effective_path, str) and os.path.isfile(
                        os.path.join(effective_path, self.client)):
                    handle_process(client=self.client, mode='kill')
                    break
            except Exception as e:
                logger.error(f"路径检测失败，错误: {e}")
            time.sleep(1)

        if effective_path is None or not isinstance(effective_path, str) or not os.path.isdir(effective_path):
            raise ValueError(f"无效路径: {effective_path}")
        config_helper(field='path', mode='w', value=effective_path)

        logger.info(f"工作路径 -> {effective_path}")
        self.ui.pathEdit.setText(effective_path)
        return None

    def client_auto_get(self):
        """自动获取客户端"""
        subprocess.Popen('start "" "tg:"', shell=True)
        time.sleep(5)

        client_map = [
            'iMe',
            'telegram',
            'Forkgram',
            '64Gram',
            'Unigram',
            'Beeper',
            'AyuGram'
        ]

        client = handle_process(client=client_map, mode='check')
        if client != '' and isinstance(client, str):
            logger.info(f"有效客户端 -> {client}")
            config_helper(field='client', mode='w', value=client)
            self.ui.clientEdit.setText(str(client))
            self.client = client
            handle_process(client=self.client, mode='kill')
        else:
            logger.warning('无效客户端')
            self.ui.clientEdit.setText('')

    def finish(self):
        """保存所有设置"""
        c = {
            'client': self.ui.clientEdit.text(),
            'path': self.ui.pathEdit.text(),
            'default': self.ui.defaultTdataEdit.text(),
            'args': [self.ui.argsWidget.item(i).text() for i in range(self.ui.argsWidget.count())]
        }
        json.dumps(c, indent=4)
        with open('configs.json', 'w') as f:
            json.dump(c, f, indent=4)
        QMessageBox.information(None, '提示', '设置保存成功.')

    def add_item(self):
        item = QListWidgetItem("New argument")
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.ui.argsWidget.addItem(item)
        self.ui.argsWidget.editItem(item)

    def del_item(self):
        selected_item = self.ui.argsWidget.currentItem()
        if selected_item:
            row = self.ui.argsWidget.row(selected_item)
            self.ui.argsWidget.takeItem(row)

    def edit_item(self, item):
        """当用户双击某个项时，进入编辑模式"""
        self.ui.argsWidget.editItem(item)

    def client_edit_double_click_event(self):
        """客户端选择事件"""
        userSelect, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "客户端主程序 (*.exe)")
        if userSelect:
            client = os.path.basename(userSelect)
            path = os.path.dirname(userSelect)
            self.ui.clientEdit.setText(client)
            self.ui.pathEdit.setText(path)

    def path_edit_double_click_event(self):
        """路径选择事件"""
        path = QFileDialog.getExistingDirectory(self, "选择客户端路径", "")
        if path:
            self.ui.pathEdit.setText(path)

    class DoubleClickFilter(QObject):
        def __init__(self, fun):
            super().__init__()
            self.fun = fun

        def eventFilter(self, obj, event):
            if event.type() == QEvent.MouseButtonDblClick:
                self.fun()
                return True
            return super().eventFilter(obj, event)
