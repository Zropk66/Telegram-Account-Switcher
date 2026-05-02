# -*- coding: utf-8 -*-
# @Time : 2025/5/7 13:12
# @Author : Zropk
import os
import sys
import winreg
from contextlib import suppress
from pathlib import Path
from threading import RLock

from PySide6.QtCore import QObject, QEvent, Qt, QRunnable, QThreadPool, Signal, Slot, \
    QRegularExpression, QPoint
from PySide6.QtGui import QRegularExpressionValidator, QValidator, QCloseEvent
from PySide6.QtWidgets import QMainWindow, QMessageBox, QFileDialog, QListWidgetItem, QStyledItemDelegate, QLineEdit, \
    QApplication, QMenu, QDialog, QFormLayout, QDialogButtonBox, QVBoxLayout, QPushButton

from src.modules import TASConfigException, TASException, Logger, ConfigManage
from src.ui.ui_settings import Ui_setting


def open_settings_window(version):
    app = QApplication.instance() or QApplication(sys.argv)
    widget = SettingsWindow(version)
    app._settings_window = widget
    widget.show()
    return app.exec()


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


class EditLabelDialog(QDialog):
    """编辑标签的对话框"""

    def __init__(self, user_id='', folder='', tag='', info='', identity='', key='', parent=None):
        super().__init__(parent)
        from src.ui.ui_edit import Ui_edit
        self.ui = Ui_edit()
        self.ui.setupUi(self)

        self._info = info
        self._identity = identity
        self._key = key

        self.ui.user_id_edit.setText(str(user_id))
        self.ui.folder_edit.setText(str(folder))
        self.ui.tag_edit.setText(str(tag))

        self.ui.show_button.clicked.connect(self.show_keys_dialog)

        self.ui.browse_button.clicked.connect(self.browse_folder)
        self.ui.confirm_button.clicked.connect(self.validate_and_accept)
        self.ui.cancel_button.clicked.connect(self.reject)
        self.ui.default_button.clicked.connect(self.set_default_and_accept)

        self.is_default = False

    def validate_inputs(self):
        """验证输入是否合法"""
        path = self.ui.folder_label.text().strip()
        tag = self.ui.tag_edit.text().strip()

        if not tag:
            QMessageBox.warning(self, "输入错误", "标签不能为空")
            return False
        if not path:
            QMessageBox.warning(self, "输入错误", "路径不能为空")
            return False
        return True

    def validate_and_accept(self):
        """验证通过后确认"""
        if self.validate_inputs():
            self.accept()

    def set_default_and_accept(self):
        """设为默认并确认"""
        if self.validate_inputs():
            self.is_default = True
            self.accept()

    def browse_folder(self):
        """打开文件夹选择对话框"""
        folder = QFileDialog.getExistingDirectory(self, "选择账户文件夹")
        if folder:
            self.ui.folder_edit.setText(folder)

    def show_keys_dialog(self):
        """显示密钥对话框"""
        from src.ui.ui_show_key import Ui_info
        dialog = QDialog(self)
        dialog.setWindowTitle("查看密钥")
        dialog.setMinimumWidth(400)
        ui = Ui_info()
        ui.setupUi(dialog)

        # 设置当前值
        ui.info_edit.setText(self._info)
        ui.identity_edit.setText(self._identity)
        ui.key_edit.setText(self._key)

        # 保存按钮
        def save_keys():
            self._info = ui.info_edit.text().strip()
            self._identity = ui.identity_edit.text().strip()
            self._key = ui.key_edit.text().strip()
            dialog.accept()

        ui.confirm_button.clicked.connect(save_keys)
        ui.cancel_button.clicked.connect(dialog.reject)

        dialog.exec()

    def get_account_data(self):
        """返回 (id, path, info, identity, key) 五元组"""
        id_val = self.ui.user_id_edit.text().strip()
        path = self.ui.folder_edit.text().strip()
        tag = self.ui.tag_edit.text().strip()
        return id_val, path, self._info, self._identity, self._key, tag


class AddAccountDialog(QDialog):
    """添加账户的对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加账户")
        self.resize(400, 200)

        layout = QFormLayout(self)

        # 账户ID
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("请输入数字ID")
        layout.addRow("账户ID:", self.id_edit)

        # 文件夹路径
        folder_layout = QVBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("请选择文件夹或手动输入路径")
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(self.browse_btn)
        layout.addRow("文件夹:", folder_layout)

        # 标签
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("可选，留空后双击可编辑")
        layout.addRow("标签(可选):", self.label_edit)

        # 操作按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def browse_folder(self):
        """打开文件夹选择对话框"""
        folder = QFileDialog.getExistingDirectory(self, "选择账户文件夹")
        if folder:
            self.folder_edit.setText(folder)

    def validate_and_accept(self):
        """校验并保存"""
        # 检查ID是否为空且为数字
        id_text = self.id_edit.text().strip()
        if not id_text:
            QMessageBox.warning(self, "输入错误", "账户ID不能为空")
            return
        if not id_text.isdigit():
            QMessageBox.warning(self, "输入错误", "账户ID必须为数字")
            return

        # 检查文件夹是否为空
        folder = self.folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "输入错误", "文件夹路径不能为空")
            return
        if not os.path.exists(folder):
            reply = QMessageBox.question(self, "路径不存在",
                                         "输入的文件夹路径不存在，是否继续添加？",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return

        self.accept()

    def get_account_data(self):
        """返回 (id, folder, label) 三元组"""
        acc_id = int(self.id_edit.text().strip())
        folder = self.folder_edit.text().strip()
        label = self.label_edit.text().strip()
        return acc_id, folder, label


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

        self.client_edit_double_click_filter = DoubleClickFilter(self.select_client_event)
        self.ui.client_edit.installEventFilter(self.client_edit_double_click_filter)
        self.ui.client_edit.setText(self.current_configs.get('client'))
        self.ui.client_edit.textChanged.connect(self.client_change_event)

        self.path_edit_double_click_filter = DoubleClickFilter(self.select_path_event)
        self.ui.path_edit.installEventFilter(self.path_edit_double_click_filter)
        self.ui.path_edit.setText(self.current_configs.get('path'))
        self.ui.path_edit.textChanged.connect(self.path_change_event)

        self.ui.search_client_button.clicked.connect(self.search_client_task)

        # 加载账户列表 (执行字段迁移)
        tags_data = self.controller.config.get_all_accounts()
        for tag_name, account_data in tags_data.items():
            data = account_data.copy()
            data['tag'] = tag_name
            item = QListWidgetItem("")
            item.setData(Qt.UserRole, data)
            self.ui.tags_widget.addItem(item)
        self.refresh_list_display()

        self.ui.tags_widget.itemDoubleClicked.connect(self.edit_item_event)

        self.ui.search_account_button.clicked.connect(self.search_account_event)
        self.ui.del_button.clicked.connect(self.del_item_event)

        self.ui.tags_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.tags_widget.customContextMenuRequested.connect(self.show_context_menu)

        self.ui.log_output.setChecked(self.current_configs.get('log_output'))
        self.ui.log_output.stateChanged.connect(self.log_output_change_event)

        self.ui.finish_button.clicked.connect(self.save_config_event)

        with suppress(AttributeError):
            self.ui.cancel_button.clicked.connect(self.close)

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

    def show_context_menu(self, pos: QPoint):
        """右键菜单"""
        item = self.ui.tags_widget.itemAt(pos)
        menu = QMenu()

        add_action = menu.addAction("添加账户")
        # 如果有选中项，则启用删除动作
        if item is not None:
            delete_action = menu.addAction("删除账户")
        else:
            delete_action = None

        # 执行菜单并获取选择的动作
        action = menu.exec(self.ui.tags_widget.mapToGlobal(pos))
        if action == add_action:
            self.add_item_event()
        elif delete_action is not None and action == delete_action:
            self.del_item_event()

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
        """解析命令行中的执行文件路径"""
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

    def refresh_list_display(self):
        """刷新列表项的显示文本"""
        default_tag = self.current_configs.get('default', '')
        for row in range(self.ui.tags_widget.count()):
            item = self.ui.tags_widget.item(row)
            data = item.data(Qt.UserRole)
            if data:
                tag = data.get('tag', '')
                id_val = str(data.get('id', ''))

                # 优先显示标签，无标签则显示 ID
                display_text = tag if tag else id_val

                if (tag and tag == default_tag) or (not tag and id_val == default_tag):
                    display_text += " [默认]"

                item.setText(display_text)

    def update_current_tags(self):
        """从列表同步数据到配置字典"""
        new_tags = {}
        count = self.ui.tags_widget.count()

        for row in range(count):
            item = self.ui.tags_widget.item(row)
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

        self.update_current_config('tags', new_tags)
        self.refresh_list_display()

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

    def search_account_event(self):
        """自动扫描账户"""
        base_path = self.ui.path_edit.text().strip()
        if not base_path or not os.path.exists(base_path):
            QMessageBox.warning(self, "警告", "请输入有效的 Telegram 客户端路径")
            return

        if not self.current_configs.get("agreed_to_decrypt", False):
            reply = QMessageBox.question(
                self,
                "解密确认",
                "这是您第一次使用寻找多账号功能。\n使用该功能需要解密该目录下的本地账户数据，您同意继续吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            self.update_current_config("agreed_to_decrypt", True)
            self.controller.save_settings(self.current_configs)

        # 扫描账户获取密钥信息
        passcode = self.controller.config.pwd
        accounts = self.controller.config.scan_accounts_from_path(base_path, passcode)
        if not accounts:
            QMessageBox.information(self, "提示", "未找到任何账户")
            return

        # 获取已存在的文件夹记录
        existing_folders = set()
        for i in range(self.ui.tags_widget.count()):
            item = self.ui.tags_widget.item(i)
            data = item.data(Qt.UserRole)
            if data and data.get('folder'):
                existing_folders.add(data.get('folder'))

        # 添加找到的账户
        added_count = 0
        for folder_name, account_data in accounts.items():
            if folder_name in existing_folders:
                continue

            data = account_data.copy()
            try:
                tag_file = Path(base_path) / folder_name / "tas_tag"
                tag_file.write_text(data.get('tag', folder_name), encoding="utf-8")
            except Exception:
                pass

            item = QListWidgetItem("")
            item.setData(Qt.UserRole, data)
            self.ui.tags_widget.addItem(item)
            added_count += 1

        self.update_current_tags()
        QMessageBox.information(self, "成功", f"已添加 {len(accounts)} 个账户")

    @Slot()
    def add_item_event(self):
        """弹出添加账户对话框"""
        dlg = EditLabelDialog("", "", "", "", "", "", self)
        if dlg.exec() == QDialog.Accepted:
            id_val, folder, info, identity, key, tag = dlg.get_account_data()
            if dlg.is_default:
                self.update_current_config('default', tag)

            if folder and tag:
                try:
                    base = Path(self.ui.path_edit.text().strip())
                    folder_path = Path(folder) if Path(folder).is_absolute() else base / folder
                    folder_path.mkdir(parents=True, exist_ok=True)
                    tag_file = folder_path / "tas_tag"
                    tag_file.write_text(tag, encoding="utf-8")
                    folder = folder_path.name
                except Exception:
                    pass

            item = QListWidgetItem("")
            # 存储完整数据
            item.setData(Qt.UserRole, {
                'tag': tag,
                'id': id_val,
                'folder': folder,
                'info': info,
                'identity': identity,
                'key': key
            })
            self.ui.tags_widget.addItem(item)
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
        """双击编辑标签"""
        data = item.data(Qt.UserRole)
        tag_name = data.get('tag', '') if data else ''

        if data:
            dlg = EditLabelDialog(
                data.get('id', ''),
                data.get('folder', ''),
                tag_name,
                data.get('info', ''),
                data.get('identity', ''),
                data.get('key', ''),
                self
            )
        else:
            # 没有存储数据，创建新的空数据
            dlg = EditLabelDialog("", "", tag_name, "", "", "", self)

        if dlg.exec() == QDialog.Accepted:
            id_val, folder, info, identity, key, tag = dlg.get_account_data()
            if dlg.is_default:
                self.update_current_config('default', tag)

            if folder and tag:
                try:
                    base = Path(self.ui.path_edit.text().strip())
                    folder_path = Path(folder) if Path(folder).is_absolute() else base / folder
                    folder_path.mkdir(parents=True, exist_ok=True)
                    tag_file = folder_path / "tas_tag"
                    tag_file.write_text(tag, encoding="utf-8")
                    folder = folder_path.name
                except Exception:
                    pass

            # 如果修改的是当前的默认账号名，需要同步更新默认值
            old_tag = data.get('tag', '')
            if old_tag and old_tag == self.current_configs.get('default'):
                self.update_current_config('default', tag)

            # 更新存储的数据
            item.setData(Qt.UserRole, {
                'tag': tag,
                'id': id_val,
                'folder': folder,
                'info': info,
                'identity': identity,
                'key': key
            })
            self.update_current_tags()

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
    def log_output_change_event(self, state):
        self.update_current_config('log_output', bool(state))

    @Slot()
    def select_client_event(self):
        """客户端选择事件"""
        user_select, _ = QFileDialog.getOpenFileName(self, "选择客户端", "", "客户端主程序 (*.exe)")
        if user_select:
            client = os.path.basename(user_select)
            path = os.path.dirname(user_select)
            self.ui.client_edit.setText(client)
            self.ui.path_edit.setText(path)
            self.update_current_config('client', client)

    @Slot()
    def select_path_event(self):
        """路径选择事件"""
        user_select = QFileDialog.getExistingDirectory(self, "选择路径", "")
        if user_select:
            self.ui.path_edit.setText(user_select)
            self.update_current_config('path', user_select)
