"""UI对话框辅助类。"""
from contextlib import suppress
from pathlib import Path
from typing import Tuple, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog

from src.core import Logger
from src.core.constants import (
    KEY_FOLDER,
    IDENTITY_FOLDER,
    TELEGRAM_IDENTITY_KEY,
    INFO_SUBFOLDER,
    TAG_FILE
)


class EditLabelDialog(QDialog):
    """账户编辑/新增对话框。"""

    def __init__(self, user_id: str = "", folder: str = "", tag: str = "",
                 info: str = "", identity: str = "", key: str = "", parent=None):
        """初始化账户标签编辑对话框。"""
        super().__init__(parent)
        from src.ui.ui_edit import Ui_edit
        self.ui = Ui_edit()
        self.ui.setupUi(self)

        self._info = info
        self._identity = identity
        self._key = key
        self.is_default = False
        self._logger = Logger()

        self.ui.user_id_edit.setText(str(user_id))
        self.ui.folder_edit.setText(str(folder))
        self.ui.tag_edit.setText(str(tag))

        self._connect_signals()

    def _connect_signals(self):
        """绑定按钮及输入框的信号槽。"""
        self.ui.show_button.clicked.connect(self.show_keys_dialog)
        self.ui.browse_button.clicked.connect(self.browse_folder)
        self.ui.confirm_button.clicked.connect(self.validate_and_accept)
        self.ui.cancel_button.clicked.connect(self.reject)
        self.ui.default_button.clicked.connect(self.set_default_and_accept)
        self.ui.folder_edit.textChanged.connect(self.auto_fill_from_folder)

    def validate_inputs(self) -> bool:
        """验证用户输入是否完整合法。"""
        from src.ui.popup import alert
        folder = self.ui.folder_edit.text().strip()
        self.auto_fill_from_folder(folder)
        tag = self.ui.tag_edit.text().strip()

        if not tag:
            alert("标签不能为空", "输入错误", "warning")
            return False
        if not folder:
            alert("路径不能为空", "输入错误", "warning")
            return False
        return True

    def validate_and_accept(self):
        """验证通过后接受对话框。"""
        if self.validate_inputs():
            self.accept()

    def set_default_and_accept(self):
        """标记该账户为默认账户并接受对话框。"""
        if self.validate_inputs():
            self.is_default = True
            self.accept()

    def browse_folder(self):
        """打开文件选择器以选择账户所在目录。"""
        folder = QFileDialog.getExistingDirectory(self, "选择账户文件夹")
        if folder:
            self.ui.folder_edit.setText(folder)

    def auto_fill_from_folder(self, folder: str):
        """解析选中目录下的数据并尝试自动填充密钥字段和标签。"""
        import base64
        folder = folder.strip()
        if not folder:
            return

        base_path = ""
        passcode = ""
        parent = self.parent()
        if parent:
            if hasattr(parent, "ui") and hasattr(parent.ui, "path_edit"):
                base_path = parent.ui.path_edit.text().strip()
            if hasattr(parent, "config") and hasattr(parent.config, "pwd"):
                passcode = parent.config.pwd

        if not base_path:
            with suppress(Exception):
                from src.core.config import ConfigService
                base_path = ConfigService().path
        if not passcode:
            with suppress(Exception):
                from src.core.config import ConfigService
                passcode = ConfigService().pwd

        folder_path = Path(folder)
        if not folder_path.is_absolute() and base_path:
            folder_path = Path(base_path) / folder

        if not folder_path.is_dir():
            return

        try:
            from src.core.crypto_service import AccountDataCryptoService
            user_id = AccountDataCryptoService.decrypt_account_id(folder_path, passcode)
            if user_id and not self.ui.user_id_edit.text().strip():
                self.ui.user_id_edit.setText(str(user_id))

            def _b64_read(file_path: Path) -> str:
                """读取并Base64编码文件。"""
                with suppress(Exception):
                    if file_path.is_file():
                        return base64.b64encode(file_path.read_bytes()).decode()
                return ""

            info_val = _b64_read(folder_path / TELEGRAM_IDENTITY_KEY / INFO_SUBFOLDER)
            identity_val = _b64_read(folder_path / IDENTITY_FOLDER)
            key_val = _b64_read(folder_path / KEY_FOLDER)

            if info_val and not self._info:
                self._info = info_val
            if identity_val and not self._identity:
                self._identity = identity_val
            if key_val and not self._key:
                self._key = key_val

            if not self.ui.tag_edit.text().strip():
                tag_file = folder_path / TAG_FILE
                tag_name = ""
                if tag_file.is_file():
                    with suppress(Exception):
                        tag_name = tag_file.read_text(encoding="utf-8").strip()
                if not tag_name:
                    tag_name = folder_path.name
                self.ui.tag_edit.setText(tag_name)
        except Exception as e:
            self._logger.error(f"解析账户文件夹失败: {e}")

    def show_keys_dialog(self):
        """展示密钥查看详细弹窗。"""
        dialog = ShowKeyDialog(self._info, self._identity, self._key, self)
        if dialog.exec() == QDialog.Accepted:
            self._info, self._identity, self._key = dialog.get_keys()

    def get_account_data(self) -> Tuple[str, str, str, str, str, str]:
        """获取配置数据字段值。"""
        id_val = self.ui.user_id_edit.text().strip()
        path = self.ui.folder_edit.text().strip()
        tag = self.ui.tag_edit.text().strip()
        return id_val, path, self._info, self._identity, self._key, tag


class ShowKeyDialog(QDialog):
    """账户密钥明细展示对话框。"""

    def __init__(self, info: str = "", identity: str = "", key: str = "", parent=None):
        """初始化密钥明细对话框并填充密钥值。"""
        super().__init__(parent)
        from src.ui.ui_show_key import Ui_info
        self.ui = Ui_info()
        self.ui.setupUi(self)

        self.ui.info_edit.setText(info)
        self.ui.identity_edit.setText(identity)
        self.ui.key_edit.setText(key)

        self._connect_signals()

    def _connect_signals(self):
        """绑定确认与取消按钮事件。"""
        self.ui.confirm_button.clicked.connect(self.accept)
        self.ui.cancel_button.clicked.connect(self.reject)

    def get_keys(self) -> Tuple[str, str, str]:
        """获取各密钥文本框的编辑值。"""
        return (
            self.ui.info_edit.text().strip(),
            self.ui.identity_edit.text().strip(),
            self.ui.key_edit.text().strip()
        )


class SettingsDialogHelper:
    """设置对话框辅助类。"""

    @staticmethod
    def handle_edit_dialog_result(
        item,
        dialog: EditLabelDialog,
        current_configs: Dict[str, Any],
        path_edit_text: str,
        update_config_callback,
        model_update_callback,
        model_add_callback,
        config_manage=None,
        refresh_display_callback=None
    ):
        """解析并同步账户编辑结果。"""
        id_val, folder, info, identity, key, tag = dialog.get_account_data()

        if dialog.is_default:
            if config_manage:
                config_manage.default = tag
            update_config_callback('default', tag)

        if folder and tag:
            with suppress(Exception):
                base = Path(path_edit_text.strip())
                folder_path = Path(folder) if Path(folder).is_absolute() else base / folder
                folder_path.mkdir(parents=True, exist_ok=True)
                (folder_path / TAG_FILE).write_text(tag, encoding="utf-8")
                folder = folder_path.name

        new_data = {'tag': tag, 'id': id_val, 'folder': folder, 'info': info, 'identity': identity, 'key': key}

        old_tag = None
        if item:
            item_data = item.data(Qt.UserRole)
            if item_data and isinstance(item_data, dict):
                old_tag = item_data.get('tag')
            model_update_callback(item, new_data)
        else:
            model_add_callback(new_data)

        if old_tag and not dialog.is_default and old_tag == current_configs.get('default'):
            update_config_callback('default', tag)

        update_config_callback('tags', config_manage.get_all_accounts() if config_manage else {})

        if dialog.is_default and refresh_display_callback:
            refresh_display_callback(tag)
