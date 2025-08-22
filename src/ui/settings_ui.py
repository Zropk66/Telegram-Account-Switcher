# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import winreg
import sys
import os

from PySide6.QtWidgets import QMainWindow, QMessageBox, QFileDialog, QListWidgetItem, QStyledItemDelegate, QLineEdit, \
    QApplication
from PySide6.QtCore import QObject, QEvent, Qt, QRunnable, QThreadPool, Signal, Slot, \
    QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator, QValidator, QCloseEvent

from threading import RLock
from pathlib import Path

from src.ui.ui_settings import Ui_setting
from src.modules import TASConfigException, TASException, Logger, ConfigManage


def open_settings_window(version):
    """打开设置窗口"""
    app = QApplication.instance() or QApplication(sys.argv)
    widget = SettingsWindow(version)
    widget.show()
    sys.exit(app.exec())


class SettingsController:
    def __init__(self):
        self.config = ConfigManage()

    def load_settings(self):
        return self.config.configs

    def save_settings(self, config_data):
        self.config.batch_update(config_data)


class NonEmptyDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        regex = QRegularExpression(r"^[^\s](.*[^\s])?$")
        validator = QRegularExpressionValidator(regex, editor)
        editor.setValidator(validator)
        return editor


class NonEmptyValidator(QValidator):
    def validate(self, input_str, pos):
        input_str = input_str.replace(' ', '')
        return QValidator.Acceptable, input_str, pos


class SignalsEmitter(QObject):
    finished = Signal(object)
    warning = Signal(object)
    error = Signal(object)
    exception = Signal(Exception)
    signal = Signal(object)


class TaskRunner(QRunnable):
    def __init__(self, func):
        super().__init__()
        self.func = func
        self.signals = SignalsEmitter()

    @Slot()
    def run(self):
        try:
            result = self.func()
            self.signals.finished.emit(result)
        except TASException as e:
            self.signals.error.emit(e)


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


class SettingsWindow(QMainWindow):
    def __init__(self, version):
        super().__init__()
        self.ui = Ui_setting()
        self.ui.setupUi(self)
        self.thread_pool = QThreadPool.globalInstance()
        self.logger = Logger()
        self.controller = SettingsController()
        self.current_configs = self.controller.load_settings()

        self.lock = RLock()

        self.ui.version_label.setText(f'TAS v{version}')

        self.client_edit_double_click_filter = DoubleClickFilter(self.client_edit_double_click_event)
        self.ui.client_edit.installEventFilter(self.client_edit_double_click_filter)
        self.ui.client_edit.setText(self.current_configs.get('client'))
        self.ui.client_edit.textChanged.connect(self.client_change_event)

        self.path_edit_double_click_filter = DoubleClickFilter(self.path_edit_double_click_event)
        self.ui.path_edit.installEventFilter(self.path_edit_double_click_filter)
        self.ui.path_edit.setText(self.current_configs.get('path'))
        self.ui.path_edit.textChanged.connect(self.path_change_event)

        self.ui.search_client_button.clicked.connect(self.search_client_task)

        self.ui.default_edit.setText(self.current_configs.get('default'))
        self.ui.default_edit.textChanged.connect(self.default_change_event)
        self.ui.default_edit.setValidator(NonEmptyValidator())

        self.ui.tags_widget.addItems(self.current_configs.get('tags'))
        self.ui.tags_widget.itemChanged.connect(self.tags_change_event)
        self.ui.tags_widget.itemDoubleClicked.connect(self.edit_item_event)
        self.ui.tags_widget.setItemDelegate(NonEmptyDelegate())

        self.ui.add_button.clicked.connect(self.add_item_event)
        self.ui.del_button.clicked.connect(self.del_item_event)

        for i in range(self.ui.tags_widget.count()):
            item = self.ui.tags_widget.item(i)
            item.setFlags(item.flags() | Qt.ItemIsEditable)

        self.ui.log_output.setChecked(self.current_configs.get('log_output'))
        self.ui.log_output.stateChanged.connect(self.log_output_change_event)

        self.ui.finish_button.clicked.connect(self.save_config_event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.controller.load_settings() != self.current_configs:
            reply = QMessageBox.question(
                self,
                'Tips',
                "配置已更改但未保存，你确定要退出程序吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()

    def _search_client(self):
        """自动查找客户端"""
        with self.lock:
            try:
                protocol_key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"tg", 0, winreg.KEY_READ)
                with winreg.OpenKey(protocol_key, r"shell\open\command") as command_key:
                    command = winreg.QueryValue(command_key, None)
                    full_path = Path(self.extract_executable_path(command)).resolve(strict=True)
                    if not full_path or not os.path.exists(full_path):
                        raise TASException('提取的客户端路径无效或文件不存在.')
                    client = os.path.basename(full_path)
                    path = os.path.dirname(full_path)
                    self.ui.client_edit.setText(client)
                    self.ui.path_edit.setText(path)
                    self.update_current_config('client', client)
                    self.update_current_config('path', path)
                    return f"有效客户端 -> {full_path}"
            except (FileNotFoundError, AttributeError) as e:
                raise TASException('无法找到客户端，请确保协议关联已安装并注册') from e
            except RuntimeError as e:
                raise TASException(f'注册表操作失败') from e
            except PermissionError as e:
                raise TASException('如果权限不足，请以管理员身份运行该程序') from e
            except OSError as e:
                raise TASException(f'系统错误({e.winerror}): {e.strerror}') from e

    @staticmethod
    def extract_executable_path(command):
        """从命令行字符串中提取可执行文件路径"""
        if not command:
            raise AttributeError("命令字符串为空")

        try:
            if command.startswith('"'):
                end_quote = command.find('"', 1)
                if end_quote != -1:
                    return command[1:end_quote]

            parts = command.split()
            if parts:
                candidate = parts[0]
                if os.path.exists(candidate):
                    return candidate

                clean_candidate = candidate.strip('"\'')
                if os.path.exists(clean_candidate):
                    return clean_candidate
                return candidate
            return command
        except AttributeError:
            raise

    def update_current_tags(self):
        new_tags = []
        count = self.ui.tags_widget.count()
        for row in range(count):
            item = self.ui.tags_widget.item(row)
            new_tags.append(item.text())
        self.update_current_config('tags', new_tags)

    def update_current_config(self, key, value):
        self.current_configs[key] = value

    @Slot()
    def save_config_event(self):
        try:
            self.controller.save_settings(self.current_configs)
            self.logger.info('配置保存成功.')
            QMessageBox.information(None, '成功', '配置已保存')
        except TASConfigException as e:
            self.logger.exception(f"配置保存失败", e)

    @Slot()
    def add_item_event(self):
        item = QListWidgetItem("New argument")
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.ui.tags_widget.addItem(item)
        self.ui.tags_widget.editItem(item)
        self.update_current_tags()

    @Slot()
    def del_item_event(self):
        selected_item = self.ui.tags_widget.currentItem()
        if selected_item:
            row = self.ui.tags_widget.row(selected_item)
            self.ui.tags_widget.takeItem(row)
            self.update_current_tags()

    @Slot()
    def edit_item_event(self, item):
        self.ui.tags_widget.editItem(item)

    @Slot()
    def search_client_task(self):
        runner = TaskRunner(self._search_client)
        runner.signals.finished.connect(self.finished_signal_event)
        runner.signals.error.connect(self.error_signal_event)
        self.thread_pool.start(runner)

    @Slot()
    def finished_signal_event(self, result):
        self.logger.info(result)

    @Slot()
    def error_signal_event(self, e):
        self.logger.error(e.message, popup=True)

    @Slot()
    def client_change_event(self, text):
        self.update_current_config('client', text)

    @Slot()
    def path_change_event(self, text):
        self.update_current_config('path', text)

    @Slot()
    def default_change_event(self, text):
        self.update_current_config('default', text)

    @Slot()
    def log_output_change_event(self, state):
        self.update_current_config('log_output', bool(state))

    @Slot()
    def tags_change_event(self):
        self.update_current_config(
            'tags',
            [
                self.ui.tags_widget.item(i).text() for i in range(self.ui.tags_widget.count())
            ]
        )

    @Slot()
    def client_edit_double_click_event(self):
        """客户端选择事件"""
        user_select, _ = QFileDialog.getOpenFileName(self, "选择客户端", "", "客户端主程序 (*.exe)")
        if user_select:
            client = os.path.basename(user_select)
            path = os.path.dirname(user_select)
            self.ui.client_edit.setText(client)
            self.ui.path_edit.setText(path)
            self.update_current_config('client', client)

    @Slot()
    def path_edit_double_click_event(self):
        """路径选择事件"""
        user_select = QFileDialog.getExistingDirectory(self, "选择客户端路径", "")
        if user_select:
            self.ui.path_edit.setText(user_select)
            self.update_current_config('path', user_select)
