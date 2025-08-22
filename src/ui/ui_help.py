# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'help.ui'
##
## Created by: Qt User Interface Compiler version 6.9.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QMetaObject, QRect,
                            Qt)
from PySide6.QtGui import (QFont)
from PySide6.QtWidgets import (QAbstractItemView, QLabel,
                               QTableWidget, QTableWidgetItem)

class Ui_help(object):
    def setupUi(self, help):
        if not help.objectName():
            help.setObjectName(u"help")
        help.resize(600, 400)
        self.args_widget = QTableWidget(help)
        if self.args_widget.columnCount() < 4:
            self.args_widget.setColumnCount(4)
        __qtablewidgetitem = QTableWidgetItem()
        self.args_widget.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.args_widget.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.args_widget.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.args_widget.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.args_widget.setObjectName(u"args_widget")
        self.args_widget.setGeometry(QRect(50, 50, 500, 300))
        self.args_widget.setAutoScroll(True)
        self.args_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.args_widget.setRowCount(0)
        self.args_widget.setColumnCount(4)
        self.title_label = QLabel(help)
        self.title_label.setObjectName(u"title_label")
        self.title_label.setGeometry(QRect(60, 9, 481, 31))
        font = QFont()
        font.setPointSize(15)
        self.title_label.setFont(font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tips_label = QLabel(help)
        self.tips_label.setObjectName(u"tips_label")
        self.tips_label.setGeometry(QRect(270, 350, 281, 20))
        font1 = QFont()
        font1.setPointSize(10)
        self.tips_label.setFont(font1)
        self.tips_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)
        self.version_label = QLabel(help)
        self.version_label.setObjectName(u"version_label")
        self.version_label.setGeometry(QRect(350, 370, 201, 16))
        self.version_label.setFont(font1)
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.retranslateUi(help)

        QMetaObject.connectSlotsByName(help)
    # setupUi

    def retranslateUi(self, help):
        help.setWindowTitle(QCoreApplication.translate("help", u"\u5e2e\u52a9\u6587\u6863", None))
        ___qtablewidgetitem = self.args_widget.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("help", u"\u5e8f\u53f7", None));
        ___qtablewidgetitem1 = self.args_widget.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("help", u"\u957f\u53c2\u6570", None));
        ___qtablewidgetitem2 = self.args_widget.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("help", u"\u77ed\u53c2\u6570", None));
        ___qtablewidgetitem3 = self.args_widget.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("help", u"\u8bf4\u660e", None));
        self.title_label.setText(QCoreApplication.translate("help", u"\u547d\u4ee4\u884c\u53c2\u6570\u8bf4\u660e", None))
        self.tips_label.setText(QCoreApplication.translate("help", u"\u6ce8\uff1a\u5728\u547d\u4ee4\u884c\u4e2d\u4f7f\u7528\u4e0a\u8ff0\u9009\u9879\u64cd\u4f5c\u7a0b\u5e8f.", None))
        self.version_label.setText("")
    # retranslateUi

