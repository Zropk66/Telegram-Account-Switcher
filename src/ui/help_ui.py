# -*- coding: utf-8 -*-
# @File ： help_ui.py
# @Time : 2025/7/24 17:17
# @Author : Zropk
import sys

from PySide6.QtWidgets import QWidget, QApplication, QTableWidgetItem, QHeaderView, QTableWidget, QAbstractItemView
from PySide6.QtCore import Slot

from src.ui.ui_help import Ui_help


def open_help_window(version):
    """打开帮助窗口"""
    app = QApplication.instance() or QApplication(sys.argv)
    widget = HelpWindow(version)
    widget.show()
    sys.exit(app.exec())


class HelpWindow(QWidget):
    def __init__(self, version):
        super().__init__()
        self.version = version
        self.ui = Ui_help()
        self.ui.setupUi(self)
        self.help_datas = [
            ("--version", "-v", "获取版本"),
            ("--help", "-h", "帮助文档"),
            ("--settings", "-c", "打开设置"),
            ("--switch", "-s", "切换指定标签的账号"),
            ("--password", "-p", "指定解密密钥"),
            ("--encrypt", "-e", "立即加密文件"),
            ("--decrypt", "-d", "立即解密文件")
        ]
        self.ui.version_label.setText(f'TAS v{self.version}')
        self.ui.args_widget.setRowCount(len(self.help_datas))
        for row, (long_opt, short_opt, desc) in enumerate(self.help_datas):
            self.ui.args_widget.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.ui.args_widget.setItem(row, 1, QTableWidgetItem(long_opt))
            self.ui.args_widget.setItem(row, 2, QTableWidgetItem(short_opt))
            self.ui.args_widget.setItem(row, 3, QTableWidgetItem(desc))

        self.ui.args_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        # self.ui.args_widget.doubleClicked.connect(self.double_click_event)

        self.ui.args_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ui.args_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.ui.args_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.ui.args_widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.ui.args_widget.verticalHeader().setVisible(False)
        self.ui.args_widget.setAlternatingRowColors(True)
        self.ui.args_widget.setEditTriggers(QTableWidget.NoEditTriggers)

    @Slot()
    def double_click_event(self, event):
        print(f'{event.row()} 行, {event.column()} 列被双击了. 数据 -> "{event.data()}".')
