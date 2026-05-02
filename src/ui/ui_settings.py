# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'settings.ui'
##
## Created by: Qt User Interface Compiler version 6.11.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QMetaObject, QRect,
                            QSize)
from PySide6.QtWidgets import (QCheckBox, QLabel, QLineEdit,
                               QListWidget, QPushButton,
                               QSizePolicy, QWidget)

class Ui_setting(object):
    def setupUi(self, setting):
        if not setting.objectName():
            setting.setObjectName(u"setting")
        setting.resize(450, 250)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(setting.sizePolicy().hasHeightForWidth())
        setting.setSizePolicy(sizePolicy)
        setting.setMinimumSize(QSize(450, 250))
        setting.setMaximumSize(QSize(450, 250))
        self.central_widget = QWidget(setting)
        self.central_widget.setObjectName(u"central_widget")
        self.central_widget.setEnabled(True)
        self.client_edit = QLineEdit(self.central_widget)
        self.client_edit.setObjectName(u"client_edit")
        self.client_edit.setGeometry(QRect(70, 20, 281, 21))
        self.client_edit.setClearButtonEnabled(False)
        self.client_label = QLabel(self.central_widget)
        self.client_label.setObjectName(u"client_label")
        self.client_label.setGeometry(QRect(20, 20, 54, 16))
        self.search_client_button = QPushButton(self.central_widget)
        self.search_client_button.setObjectName(u"search_client_button")
        self.search_client_button.setGeometry(QRect(360, 20, 75, 51))
        self.path_label = QLabel(self.central_widget)
        self.path_label.setObjectName(u"path_label")
        self.path_label.setGeometry(QRect(20, 50, 54, 16))
        self.path_edit = QLineEdit(self.central_widget)
        self.path_edit.setObjectName(u"path_edit")
        self.path_edit.setGeometry(QRect(70, 50, 281, 21))
        self.path_edit.setClearButtonEnabled(False)
        self.tags_label = QLabel(self.central_widget)
        self.tags_label.setObjectName(u"tags_label")
        self.tags_label.setGeometry(QRect(20, 80, 54, 16))
        self.tags_widget = QListWidget(self.central_widget)
        self.tags_widget.setObjectName(u"tags_widget")
        self.tags_widget.setGeometry(QRect(70, 80, 281, 121))
        self.search_account_button = QPushButton(self.central_widget)
        self.search_account_button.setObjectName(u"search_account_button")
        self.search_account_button.setGeometry(QRect(360, 100, 75, 24))
        self.del_button = QPushButton(self.central_widget)
        self.del_button.setObjectName(u"del_button")
        self.del_button.setGeometry(QRect(360, 130, 75, 24))
        self.cancel_button = QPushButton(self.central_widget)
        self.cancel_button.setObjectName(u"cancel_button")
        self.cancel_button.setGeometry(QRect(360, 210, 75, 24))
        self.log_output = QCheckBox(self.central_widget)
        self.log_output.setObjectName(u"log_output")
        self.log_output.setGeometry(QRect(360, 170, 82, 20))
        self.version_label = QLabel(self.central_widget)
        self.version_label.setObjectName(u"version_label")
        self.version_label.setGeometry(QRect(10, 200, 211, 16))
        self.finish_button = QPushButton(self.central_widget)
        self.finish_button.setObjectName(u"finish_button")
        self.finish_button.setGeometry(QRect(270, 210, 75, 24))
        setting.setCentralWidget(self.central_widget)

        self.retranslateUi(setting)

        QMetaObject.connectSlotsByName(setting)
    # setupUi

    def retranslateUi(self, setting):
        setting.setWindowTitle(QCoreApplication.translate("setting", u"\u8bbe\u7f6e", None))
#if QT_CONFIG(tooltip)
        self.client_edit.setToolTip(QCoreApplication.translate("setting", u"\u5728\u8fd9\u91cc\u8f93\u5165\u4f60\u6240\u4f7f\u7528\u7684Telegram\u5ba2\u6237\u7aef\u540d\u79f0", None))
#endif // QT_CONFIG(tooltip)
        self.client_edit.setPlaceholderText(QCoreApplication.translate("setting", u"\u8bf7\u8f93\u5165\u5ba2\u6237\u7aef\u7684\u540d\u79f0", None))
        self.client_label.setText(QCoreApplication.translate("setting", u"\u5ba2\u6237\u7aef", None))
#if QT_CONFIG(tooltip)
        self.search_client_button.setToolTip(QCoreApplication.translate("setting", u"\u81ea\u52a8\u83b7\u53d6\u5ba2\u6237\u7aef\u540d\u79f0", None))
#endif // QT_CONFIG(tooltip)
        self.search_client_button.setText(QCoreApplication.translate("setting", u"\u81ea\u52a8\u83b7\u53d6", None))
        self.path_label.setText(QCoreApplication.translate("setting", u"\u8def\u5f84", None))
#if QT_CONFIG(tooltip)
        self.path_edit.setToolTip(QCoreApplication.translate("setting", u"\u5728\u8fd9\u91cc\u8f93\u5165\u4f60\u6240\u4f7f\u7528\u7684Telegram\u5ba2\u6237\u7aef\u8def\u5f84", None))
#endif // QT_CONFIG(tooltip)
        self.path_edit.setPlaceholderText(QCoreApplication.translate("setting", u"\u8bf7\u8f93\u5165\u5ba2\u6237\u7aef\u8def\u5f84", None))
        self.tags_label.setText(QCoreApplication.translate("setting", u"\u53c2\u6570", None))
#if QT_CONFIG(tooltip)
        self.tags_widget.setToolTip(QCoreApplication.translate("setting", u"\u5728\u8fd9\u91cc\u6dfb\u52a0\u5907\u7528\u767b\u5f55\u7684\u8d26\u6237\u6807\u7b7e", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.search_account_button.setToolTip(QCoreApplication.translate("setting", u"\u6dfb\u52a0\u53c2\u6570", None))
#endif // QT_CONFIG(tooltip)
        self.search_account_button.setText(QCoreApplication.translate("setting", u"\u67e5\u627e\u8d26\u6237", None))
#if QT_CONFIG(tooltip)
        self.del_button.setToolTip(QCoreApplication.translate("setting", u"\u5220\u9664\u53c2\u6570", None))
#endif // QT_CONFIG(tooltip)
        self.del_button.setText(QCoreApplication.translate("setting", u"\u5220\u9664", None))
#if QT_CONFIG(tooltip)
        self.cancel_button.setToolTip(QCoreApplication.translate("setting", u"\u4fdd\u5b58\u914d\u7f6e", None))
#endif // QT_CONFIG(tooltip)
        self.cancel_button.setText(QCoreApplication.translate("setting", u"\u53d6\u6d88", None))
#if QT_CONFIG(tooltip)
        self.log_output.setToolTip(QCoreApplication.translate("setting", u"\u63a7\u5236\u65e5\u5fd7\u662f\u5426\u5199\u5165\u5230\u6587\u4ef6", None))
#endif // QT_CONFIG(tooltip)
        self.log_output.setText(QCoreApplication.translate("setting", u"\u65e5\u5fd7\u8f93\u51fa", None))
        self.version_label.setText("")
#if QT_CONFIG(tooltip)
        self.finish_button.setToolTip(QCoreApplication.translate("setting", u"\u4fdd\u5b58\u914d\u7f6e", None))
#endif // QT_CONFIG(tooltip)
        self.finish_button.setText(QCoreApplication.translate("setting", u"\u4fdd\u5b58", None))
    # retranslateUi

