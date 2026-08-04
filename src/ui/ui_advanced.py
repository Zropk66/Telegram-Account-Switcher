# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'advanced.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QMetaObject, QRect,
                            QSize)
from PySide6.QtWidgets import (QCheckBox, QComboBox, QLabel, QPushButton, QSizePolicy)

class Ui_advanced(object):
    def setupUi(self, advanced):
        if not advanced.objectName():
            advanced.setObjectName(u"advanced")
        advanced.resize(260, 235)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(advanced.sizePolicy().hasHeightForWidth())
        advanced.setSizePolicy(sizePolicy)
        advanced.setMinimumSize(QSize(260, 235))
        advanced.setMaximumSize(QSize(260, 235))
        self.mode_label = QLabel(advanced)
        self.mode_label.setObjectName(u"mode_label")
        self.mode_label.setGeometry(QRect(20, 20, 70, 24))
        self.launch_mode_combo = QComboBox(advanced)
        self.launch_mode_combo.setObjectName(u"launch_mode_combo")
        self.launch_mode_combo.setGeometry(QRect(95, 20, 140, 24))
        self.fallback = QCheckBox(advanced)
        self.fallback.setObjectName(u"fallback")
        self.fallback.setGeometry(QRect(20, 55, 215, 20))
        self.single_instance = QCheckBox(advanced)
        self.single_instance.setObjectName(u"single_instance")
        self.single_instance.setGeometry(QRect(20, 85, 215, 20))
        self.log_output = QCheckBox(advanced)
        self.log_output.setObjectName(u"log_output")
        self.log_output.setGeometry(QRect(20, 115, 215, 20))
        self.isolate_appid = QCheckBox(advanced)
        self.isolate_appid.setObjectName(u"isolate_appid")
        self.isolate_appid.setGeometry(QRect(20, 145, 215, 20))
        self.confirm_button = QPushButton(advanced)
        self.confirm_button.setObjectName(u"confirm_button")
        self.confirm_button.setGeometry(QRect(80, 190, 75, 24))
        self.cancel_button = QPushButton(advanced)
        self.cancel_button.setObjectName(u"cancel_button")
        self.cancel_button.setGeometry(QRect(165, 190, 75, 24))

        self.retranslateUi(advanced)

        QMetaObject.connectSlotsByName(advanced)
    # setupUi

    def retranslateUi(self, advanced):
        advanced.setWindowTitle(QCoreApplication.translate("advanced", u"\u9ad8\u7ea7\u8bbe\u7f6e", None))
        self.mode_label.setText(QCoreApplication.translate("advanced", u"\u542f\u52a8\u6a21\u5f0f", None))
#if QT_CONFIG(tooltip)
        self.launch_mode_combo.setToolTip(QCoreApplication.translate("advanced", u"\u9009\u62e9\u8d26\u6237\u5207\u6362\u7684\u542f\u52a8\u6a21\u5f0f", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.fallback.setToolTip(QCoreApplication.translate("advanced", u"\u63a7\u5236hook\u6a21\u5f0f\u5904\u7406\u5931\u8d25\u65f6\u662f\u5426\u964d\u56de\u94fe\u63a5\u6a21\u5f0f", None))
#endif // QT_CONFIG(tooltip)
        self.fallback.setText(QCoreApplication.translate("advanced", u"\u964d\u7ea7\u5904\u7406", None))
#if QT_CONFIG(tooltip)
        self.single_instance.setToolTip(QCoreApplication.translate("advanced", u"\u9650\u5236\u53ea\u80fd\u8fd0\u884c\u4e00\u4e2aTAS\u4e3b\u7a0b\u5e8f\u8fdb\u7a0b", None))
#endif // QT_CONFIG(tooltip)
        self.single_instance.setText(QCoreApplication.translate("advanced", u"\u5168\u5c40\u5355\u4f8b", None))
#if QT_CONFIG(tooltip)
        self.log_output.setToolTip(QCoreApplication.translate("advanced", u"\u63a7\u5236\u65e5\u5fd7\u662f\u5426\u5199\u5165\u5230\u6587\u4ef6", None))
#endif // QT_CONFIG(tooltip)
        self.log_output.setText(QCoreApplication.translate("advanced", u"\u65e5\u5fd7\u8f93\u51fa", None))
#if QT_CONFIG(tooltip)
        self.isolate_appid.setToolTip(QCoreApplication.translate("advanced", u"\u9694\u79bb AppUserModelID \u4ee5\u963b\u6b62\u4efb\u52a1\u680f\u56fe\u6807\u81ea\u52a8\u5408\u5e76", None))
#endif // QT_CONFIG(tooltip)
        self.isolate_appid.setText(QCoreApplication.translate("advanced", u"AppID \u9694\u79bb", None))
#if QT_CONFIG(tooltip)
        self.confirm_button.setToolTip(QCoreApplication.translate("advanced", u"\u786e\u8ba4", None))
#endif // QT_CONFIG(tooltip)
        self.confirm_button.setText(QCoreApplication.translate("advanced", u"\u786e\u8ba4", None))
#if QT_CONFIG(tooltip)
        self.cancel_button.setToolTip(QCoreApplication.translate("advanced", u"\u53d6\u6d88", None))
#endif // QT_CONFIG(tooltip)
        self.cancel_button.setText(QCoreApplication.translate("advanced", u"\u53d6\u6d88", None))
    # retranslateUi

