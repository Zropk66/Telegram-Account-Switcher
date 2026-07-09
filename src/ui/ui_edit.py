# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'edit.ui'
##
## Created by: Qt User Interface Compiler version 6.11.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QRect
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QSizePolicy


class Ui_edit(object):
    def setupUi(self, edit):
        if not edit.objectName():
            edit.setObjectName(u"edit")
        edit.resize(335, 145)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(edit.sizePolicy().hasHeightForWidth())
        edit.setSizePolicy(sizePolicy)
        self.tag_edit = QLineEdit(edit)
        self.tag_edit.setObjectName(u"tag_edit")
        self.tag_edit.setGeometry(QRect(60, 80, 181, 21))
        self.tag_edit.setClearButtonEnabled(False)
        self.cancel_button = QPushButton(edit)
        self.cancel_button.setObjectName(u"cancel_button")
        self.cancel_button.setGeometry(QRect(250, 110, 71, 21))
        self.user_id_edit = QLineEdit(edit)
        self.user_id_edit.setObjectName(u"user_id_edit")
        self.user_id_edit.setGeometry(QRect(60, 20, 261, 21))
        self.user_id_edit.setClearButtonEnabled(False)
        self.tag_label = QLabel(edit)
        self.tag_label.setObjectName(u"tag_label")
        self.tag_label.setGeometry(QRect(10, 80, 54, 16))
        self.folder_edit = QLineEdit(edit)
        self.folder_edit.setObjectName(u"folder_edit")
        self.folder_edit.setGeometry(QRect(60, 50, 181, 21))
        self.folder_edit.setClearButtonEnabled(False)
        self.user_id_label = QLabel(edit)
        self.user_id_label.setObjectName(u"user_id_label")
        self.user_id_label.setGeometry(QRect(10, 20, 54, 16))
        self.folder_label = QLabel(edit)
        self.folder_label.setObjectName(u"folder_label")
        self.folder_label.setGeometry(QRect(10, 50, 54, 16))
        self.confirm_button = QPushButton(edit)
        self.confirm_button.setObjectName(u"confirm_button")
        self.confirm_button.setGeometry(QRect(170, 110, 71, 21))
        self.show_button = QPushButton(edit)
        self.show_button.setObjectName(u"show_button")
        self.show_button.setGeometry(QRect(60, 110, 71, 21))
        self.browse_button = QPushButton(edit)
        self.browse_button.setObjectName(u"browse_button")
        self.browse_button.setGeometry(QRect(250, 50, 71, 21))
        self.default_button = QPushButton(edit)
        self.default_button.setObjectName(u"default_button")
        self.default_button.setGeometry(QRect(250, 80, 71, 21))

        self.retranslateUi(edit)

        QMetaObject.connectSlotsByName(edit)
    # setupUi

    def retranslateUi(self, edit):
        edit.setWindowTitle(QCoreApplication.translate("edit", u"\u8be6\u60c5", None))
#if QT_CONFIG(tooltip)
        self.tag_edit.setToolTip(QCoreApplication.translate("edit", u"\u5728\u8fd9\u91cc\u8f93\u5165\u8d26\u6237\u6807\u7b7e", None))
#endif // QT_CONFIG(tooltip)
        self.tag_edit.setPlaceholderText(QCoreApplication.translate("edit", u"\u8bf7\u8f93\u5165\u8d26\u6237\u6807\u7b7e(\u5fc5\u987b)", None))
#if QT_CONFIG(tooltip)
        self.cancel_button.setToolTip(QCoreApplication.translate("edit", u"\u53d6\u6d88", None))
#endif // QT_CONFIG(tooltip)
        self.cancel_button.setText(QCoreApplication.translate("edit", u"\u53d6\u6d88", None))
#if QT_CONFIG(tooltip)
        self.user_id_edit.setToolTip(QCoreApplication.translate("edit", u"\u5728\u8fd9\u91cc\u8f93\u5165\u4f60\u7684\u7528\u6237ID", None))
#endif // QT_CONFIG(tooltip)
        self.user_id_edit.setPlaceholderText(QCoreApplication.translate("edit", u"\u8bf7\u8f93\u5165\u4f60\u7684\u7528\u6237ID(\u53ef\u9009)", None))
        self.tag_label.setText(QCoreApplication.translate("edit", u"\u6807\u7b7e", None))
#if QT_CONFIG(tooltip)
        self.folder_edit.setToolTip(QCoreApplication.translate("edit", u"\u5728\u8fd9\u91cc\u8f93\u5165\u4f60\u7684\u8d26\u6237\u6587\u4ef6\u5939\u8def\u5f84", None))
#endif // QT_CONFIG(tooltip)
        self.folder_edit.setPlaceholderText(QCoreApplication.translate("edit", u"\u8bf7\u8f93\u5165\u8d26\u6237\u6587\u4ef6\u5939\u8def\u5f84(\u5fc5\u987b)", None))
        self.user_id_label.setText(QCoreApplication.translate("edit", u"ID", None))
        self.folder_label.setText(QCoreApplication.translate("edit", u"\u8def\u5f84", None))
#if QT_CONFIG(tooltip)
        self.confirm_button.setToolTip(QCoreApplication.translate("edit", u"\u786e\u8ba4", None))
#endif // QT_CONFIG(tooltip)
        self.confirm_button.setText(QCoreApplication.translate("edit", u"\u786e\u8ba4", None))
#if QT_CONFIG(tooltip)
        self.show_button.setToolTip(QCoreApplication.translate("edit", u"\u663e\u793a\u767b\u5f55\u6240\u9700\u7f16\u7801\u540e\u7684\u5185\u5bb9", None))
#endif // QT_CONFIG(tooltip)
        self.show_button.setText(QCoreApplication.translate("edit", u"keys", None))
#if QT_CONFIG(tooltip)
        self.browse_button.setToolTip(QCoreApplication.translate("edit", u"\u9009\u62e9\u8d26\u6237\u6587\u4ef6\u5939\u76ee\u5f55", None))
#endif // QT_CONFIG(tooltip)
        self.browse_button.setText(QCoreApplication.translate("edit", u"\u6d4f\u89c8", None))
#if QT_CONFIG(tooltip)
        self.default_button.setToolTip(QCoreApplication.translate("edit", u"\u5c06\u8be5\u8d26\u6237\u8bbe\u5b9a\u4e3a\u9ed8\u8ba4\u767b\u5f55", None))
#endif // QT_CONFIG(tooltip)
        self.default_button.setText(QCoreApplication.translate("edit", u"\u8bbe\u4e3a\u9ed8\u8ba4", None))
    # retranslateUi

