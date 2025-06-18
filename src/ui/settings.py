# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import os

from PySide6.QtCore import QObject, QEvent, Qt, QRunnable, QThreadPool, QProcess, QUrl, Signal, Slot, QRegularExpression
from PySide6.QtGui import QDesktopServices, QRegularExpressionValidator
from PySide6.QtWidgets import QMainWindow, QMessageBox, QFileDialog, QListWidgetItem, QStyledItemDelegate, QLineEdit

from src.ui.ui_settings import Ui_setting

from src.utils import Logger, ConfigManage, ConfigError, get_process_path, check_process_alive, try_kill_process, \
    try_find_client


class SettingsController:
    def __init__(self):
        self.config = ConfigManage()

    def load_settings(self):
        return self.config.configs

    def save_settings(self, config_data):
        self.config.batch_update(config_data)


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_setting()
        self.ui.setupUi(self)
        self.thread_pool = QThreadPool.globalInstance()
        self.logger = Logger()
        self.controller = SettingsController()
        self.current_configs = self.controller.load_settings()

        self.lock = False

        self.client_edit_double_click_filter = DoubleClickFilter(self.client_edit_double_click_event)
        self.ui.client_edit.installEventFilter(self.client_edit_double_click_filter)
        self.ui.client_edit.setText(self.current_configs.get('client'))
        self.ui.client_button.clicked.connect(self.start_get_client_task)

        self.path_edit_double_click_filter = DoubleClickFilter(self.path_edit_double_click_event)
        self.ui.path_edit.installEventFilter(self.path_edit_double_click_filter)
        self.ui.path_edit.setText(self.current_configs.get('path'))
        self.ui.path_button.clicked.connect(self.start_get_path_task)

        self.ui.default_edit.setText(self.current_configs.get('default'))
        self.ui.default_edit.textChanged.connect(self.default_changed)

        self.ui.tags_widget.addItems(self.current_configs.get('tags'))
        self.ui.tags_widget.itemChanged.connect(self.tags_changed)
        self.ui.tags_widget.itemDoubleClicked.connect(self.edit_item)
        self.ui.tags_widget.setItemDelegate(NonEmptyDelegate())
        self.ui.add_button.clicked.connect(self.add_item)
        self.ui.del_button.clicked.connect(self.del_item)

        for i in range(self.ui.tags_widget.count()):
            item = self.ui.tags_widget.item(i)
            item.setFlags(item.flags() | Qt.ItemIsEditable)

        self.ui.log_output.setChecked(self.controller.config.log_output)
        self.ui.log_output.stateChanged.connect(self.log_output_changed)

        self.ui.finish_button.clicked.connect(self.finish)

    def closeEvent(self, event):
        if self.controller.load_settings() != self.current_configs:
            reply = QMessageBox.question(self, 'Tips',
                                         "配置项未保存，你确定要退出程序吗？",
                                         QMessageBox.Yes | QMessageBox.No,
                                         QMessageBox.No)

            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()

    def start_get_client_task(self):
        runner = TaskRunner(self.get_client)
        runner.signals.signal.connect(self.on_task_signal)
        self.thread_pool.start(runner)

    def start_get_path_task(self):
        runner = TaskRunner(self.get_path)
        runner.signals.signal.connect(self.on_task_signal)
        self.thread_pool.start(runner)

    def default_changed(self, text):
        self.current_configs['default'] = text

    def tags_changed(self):
        self.current_configs['tags'] = [self.ui.tags_widget.item(i).text() for i in range(self.ui.tags_widget.count())]

    def log_output_changed(self, state):
        self.current_configs['log_output'] = bool(state)

    @Slot(object)
    def on_task_finished(self, result):
        pass

    @Slot(Exception)
    def on_task_error(self, result):
        pass

    @Slot(bool)
    def on_task_signal(self, result):
        pass

    def get_client(self) -> bool:
        """自动获取客户端"""
        if self.lock: return False
        self.lock = True

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
        result = False

        for _ in range(10):
            if process.waitForFinished(1000): break
            client = try_find_client(client_map)
            if client: break
        if not client is None:
            self.logger.info(f"有效客户端 -> {client}")
            ConfigManage().client = client
            self.ui.client_edit.setText(str(client))
            self.current_configs['client'] = client
            result = True
        else:
            self.logger.warning('无效客户端.')
            self.ui.client_edit.setText('')
        try_kill_process(client)
        self.lock = False
        return result

    def get_path(self) -> bool:
        """自动获取路径"""
        if self.lock: return False
        self.lock = True
        client = self.current_configs.get('client')

        if not client:
            self.logger.warning('客户端名称未设置，请先获取客户端名称后重试.')
        try:
            QDesktopServices.openUrl(QUrl("tg:"))
        except Exception as e:
            self.logger.error(e)
        if not check_process_alive(client):
            self.logger.warning("无法获取到路径，您使用的telegram可能不在我们的预设池里，请手动设置.")
            return False
        effective_path = get_process_path(str(client))
        if not (isinstance(effective_path, str) and os.path.isfile(
                os.path.join(str(effective_path), str(client)))):
            raise ValueError(f"无效路径: {effective_path}")
        try_kill_process(str(client))
        self.logger.info(f"有效路径 -> {effective_path}")
        self.current_configs['path'] = effective_path
        self.ui.path_edit.setText(effective_path)
        self.lock = False
        try_kill_process(client)
        return True

    def finish(self):
        try:
            self.controller.save_settings(self.current_configs)
            QMessageBox.information(None, '成功', '配置已保存')
        except ConfigError as e:
            self.logger.error(f"配置保存失败: {e.code}-{e.message}")
            QMessageBox.critical(None, '失败', f"保存失败: {e.message}")

    def add_item(self):
        item = QListWidgetItem("New argument")
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.ui.tags_widget.addItem(item)
        self.ui.tags_widget.editItem(item)
        self.update_current_tags()


    def del_item(self):
        selected_item = self.ui.tags_widget.currentItem()
        if selected_item:
            row = self.ui.tags_widget.row(selected_item)
            self.ui.tags_widget.takeItem(row)
            self.update_current_tags()

    def update_current_tags(self):
        new_tags = []
        count = self.ui.tags_widget.count()
        for row in range(count):
            item = self.ui.tags_widget.item(row)
            new_tags.append(item.text())
        self.current_configs['tags'] = new_tags

    def edit_item(self, item):
        """当用户双击某个项时，进入编辑模式"""
        self.ui.tags_widget.editItem(item)

    def client_edit_double_click_event(self):
        """客户端选择事件"""
        user_select, _ = QFileDialog.getOpenFileName(self, "选择客户端", "", "客户端主程序 (*.exe)")
        if user_select:
            client = os.path.basename(user_select)
            path = os.path.dirname(user_select)
            self.ui.client_edit.setText(client)
            self.ui.path_edit.setText(path)
            self.current_configs['client'] = client

    def path_edit_double_click_event(self):
        """路径选择事件"""
        path = QFileDialog.getExistingDirectory(self, "选择客户端路径", "")
        if path: self.ui.path_edit.setText(path)
        self.current_configs['path'] = path


class NonEmptyDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        regex = QRegularExpression(r"^\S+.*")
        validator = QRegularExpressionValidator(regex, editor)
        editor.setValidator(validator)
        return editor


class SignalsEmitter(QObject):
    finished = Signal(object)
    error = Signal(Exception)
    signal = Signal(object)


class TaskRunner(QRunnable):
    def __init__(self, func):
        super().__init__()
        self.func = func
        self.signals = SignalsEmitter()

    def run(self):
        try:
            result = self.func()
            self.signals.signal.emit(result)
        except Exception:
            self.signals.signal.emit(False)


class DoubleClickFilter(QObject):
    """通用双击事件过滤器"""

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
