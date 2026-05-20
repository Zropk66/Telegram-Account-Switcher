"""
对话框组件模块。

封装账户信息编辑、密钥显示及配置处理相关的 UI 对话框。
"""

from contextlib import suppress
from pathlib import Path
from typing import Tuple, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog

from src.core import Logger


class EditLabelDialog(QDialog):
    """
    账户信息编辑/新增对话框。

    用户通过此界面输入账户ID、映射文件夹及相关加密密钥。
    """

    def __init__(self, user_id: str = "", folder: str = "", tag: str = "",
                 info: str = "", identity: str = "", key: str = "", parent=None):
        """初始化。"""
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
        """绑定 UI 操作信号。"""
        self.ui.show_button.clicked.connect(self.show_keys_dialog)
        self.ui.browse_button.clicked.connect(self.browse_folder)
        self.ui.confirm_button.clicked.connect(self.validate_and_accept)
        self.ui.cancel_button.clicked.connect(self.reject)
        self.ui.default_button.clicked.connect(self.set_default_and_accept)

    def validate_inputs(self) -> bool:
        """检查用户输入是否完整合法。"""
        from src.ui.popup import alert
        folder = self.ui.folder_edit.text().strip()
        tag = self.ui.tag_edit.text().strip()

        if not tag:
            alert("标签不能为空", "输入错误", "warning")
            return False
        if not folder:
            alert("路径不能为空", "输入错误", "warning")
            return False
        return True

    def validate_and_accept(self):
        """验证后确认操作。"""
        if self.validate_inputs():
            self.accept()

    def set_default_and_accept(self):
        """将当前账户标记为默认并确认。"""
        if self.validate_inputs():
            self.is_default = True
            self.accept()

    def browse_folder(self):
        """启动系统目录浏览器，选择账户文件夹。"""
        folder = QFileDialog.getExistingDirectory(self, "选择账户文件夹")
        if folder:
            self.ui.folder_edit.setText(folder)

    def show_keys_dialog(self):
        """显示密钥编辑子对话框。"""
        dialog = ShowKeyDialog(self._info, self._identity, self._key, self)
        if dialog.exec() == QDialog.Accepted:
            self._info, self._identity, self._key = dialog.get_keys()

    def get_account_data(self) -> Tuple[str, str, str, str, str, str]:
        """返回当前界面配置的账户完整数据。"""
        id_val = self.ui.user_id_edit.text().strip()
        path = self.ui.folder_edit.text().strip()
        tag = self.ui.tag_edit.text().strip()
        return id_val, path, self._info, self._identity, self._key, tag


class ShowKeyDialog(QDialog):
    """账户密钥明细查看与修改对话框。"""

    def __init__(self, info: str = "", identity: str = "", key: str = "", parent=None):
        """初始化。"""
        super().__init__(parent)
        from src.ui.ui_show_key import Ui_info
        self.ui = Ui_info()
        self.ui.setupUi(self)

        self.ui.info_edit.setText(info)
        self.ui.identity_edit.setText(identity)
        self.ui.key_edit.setText(key)

        self._connect_signals()

    def _connect_signals(self):
        """绑定确认与取消操作。"""
        self.ui.confirm_button.clicked.connect(self.accept)
        self.ui.cancel_button.clicked.connect(self.reject)

    def get_keys(self) -> Tuple[str, str, str]:
        """提取并返回当前编辑的密钥组。"""
        return (
            self.ui.info_edit.text().strip(),
            self.ui.identity_edit.text().strip(),
            self.ui.key_edit.text().strip()
        )


class SettingsDialogHelper:
    """辅助类：将对话框交互结果与核心业务模型同步。"""

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
        """
        解析对话框操作结果并更新至配置持久层与 UI 列表模型。

        若检测到默认账户切换或路径变更，会自动修正配置状态并处理 `tas_tag` 文件同步。
        """
        id_val, folder, info, identity, key, tag = dialog.get_account_data()

        # 处理默认账户更新
        if dialog.is_default:
            if config_manage:
                config_manage.default = tag
            update_config_callback('default', tag)

        # 若路径为相对路径，基于基准路径完成创建与 tag 关联
        if folder and tag:
            with suppress(Exception):
                base = Path(path_edit_text.strip())
                folder_path = Path(folder) if Path(folder).is_absolute() else base / folder
                folder_path.mkdir(parents=True, exist_ok=True)
                (folder_path / "tas_tag").write_text(tag, encoding="utf-8")
                folder = folder_path.name

        new_data = {'tag': tag, 'id': id_val, 'folder': folder, 'info': info, 'identity': identity, 'key': key}

        # 更新模型条目
        old_tag = None
        if item:
            item_data = item.data(Qt.UserRole)
            if item_data and isinstance(item_data, dict):
                old_tag = item_data.get('tag')
            model_update_callback(item, new_data)
        else:
            model_add_callback(new_data)

        # 若原默认账户标识发生重命名，同步修正配置
        if old_tag and not dialog.is_default and old_tag == current_configs.get('default'):
            update_config_callback('default', tag)

        update_config_callback('tags', config_manage.get_all_accounts() if config_manage else {})

        if dialog.is_default and refresh_display_callback:
            refresh_display_callback(tag)
