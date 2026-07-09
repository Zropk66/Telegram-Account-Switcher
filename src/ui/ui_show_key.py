# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'show_key.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QRect
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QSizePolicy


class Ui_info(object):
    def setupUi(self, info):
        if not info.objectName():
            info.setObjectName(u"info")
        info.resize(335, 145)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(info.sizePolicy().hasHeightForWidth())
        info.setSizePolicy(sizePolicy)
        self.key_edit = QLineEdit(info)
        self.key_edit.setObjectName(u"key_edit")
        self.key_edit.setGeometry(QRect(60, 80, 261, 21))
        self.key_edit.setClearButtonEnabled(False)
        self.cancel_button = QPushButton(info)
        self.cancel_button.setObjectName(u"cancel_button")
        self.cancel_button.setGeometry(QRect(250, 110, 71, 21))
        self.info_edit = QLineEdit(info)
        self.info_edit.setObjectName(u"info_edit")
        self.info_edit.setGeometry(QRect(60, 20, 261, 21))
        self.info_edit.setClearButtonEnabled(False)
        self.key_label = QLabel(info)
        self.key_label.setObjectName(u"key_label")
        self.key_label.setGeometry(QRect(10, 80, 54, 16))
        self.identity_edit = QLineEdit(info)
        self.identity_edit.setObjectName(u"identity_edit")
        self.identity_edit.setGeometry(QRect(60, 50, 261, 21))
        self.identity_edit.setClearButtonEnabled(False)
        self.info_label = QLabel(info)
        self.info_label.setObjectName(u"info_label")
        self.info_label.setGeometry(QRect(10, 20, 54, 16))
        self.identity_label = QLabel(info)
        self.identity_label.setObjectName(u"identity_label")
        self.identity_label.setGeometry(QRect(10, 50, 54, 16))
        self.confirm_button = QPushButton(info)
        self.confirm_button.setObjectName(u"confirm_button")
        self.confirm_button.setGeometry(QRect(170, 110, 71, 21))

        self.retranslateUi(info)

        QMetaObject.connectSlotsByName(info)
    # setupUi

    def retranslateUi(self, info):
        info.setWindowTitle(QCoreApplication.translate("info", u"\u8be6\u60c5", None))
#if QT_CONFIG(tooltip)
        self.key_edit.setToolTip(QCoreApplication.translate("info", u"\u8fd9\u662f\u4f60\u8d26\u6237\u5168\u5c40\u94a5\u5319\u4e32", None))
#endif // QT_CONFIG(tooltip)
        self.key_edit.setPlaceholderText(QCoreApplication.translate("info", u"\u5168\u5c40\u94a5\u5319\u4e32", None))
#if QT_CONFIG(tooltip)
        self.cancel_button.setToolTip(QCoreApplication.translate("info", u"\u5220\u9664\u53c2\u6570", None))
#endif // QT_CONFIG(tooltip)
        self.cancel_button.setText(QCoreApplication.translate("info", u"\u53d6\u6d88", None))
#if QT_CONFIG(tooltip)
        self.info_edit.setToolTip(QCoreApplication.translate("info", u"\u8fd9\u662f\u4f60\u8d26\u6237\u7684\u4e2a\u4eba\u8d44\u6599", None))
#endif // QT_CONFIG(tooltip)
        self.info_edit.setPlaceholderText(QCoreApplication.translate("info", u"\u4e2a\u4eba\u8d44\u6599", None))
        self.key_label.setText(QCoreApplication.translate("info", u"key", None))
#if QT_CONFIG(tooltip)
        self.identity_edit.setToolTip(QCoreApplication.translate("info", u"\u8fd9\u662f\u4f60\u8d26\u6237\u7684\u8d26\u6237\u8eab\u4efd\u8bc1", None))
#endif // QT_CONFIG(tooltip)
        self.identity_edit.setPlaceholderText(QCoreApplication.translate("info", u"\u8d26\u6237\u8eab\u4efd\u8bc1", None))
        self.info_label.setText(QCoreApplication.translate("info", u"info", None))
        self.identity_label.setText(QCoreApplication.translate("info", u"identity", None))
#if QT_CONFIG(tooltip)
        self.confirm_button.setToolTip(QCoreApplication.translate("info", u"\u4fdd\u5b58\u914d\u7f6e", None))
#endif // QT_CONFIG(tooltip)
        self.confirm_button.setText(QCoreApplication.translate("info", u"\u786e\u8ba4", None))
    # retranslateUi

