# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'settings.ui'
##
## Created by: Qt User Interface Compiler version 6.8.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QPushButton, QSizePolicy,
    QWidget)

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
        self.centralwidget = QWidget(setting)
        self.centralwidget.setObjectName(u"centralwidget")
        self.centralwidget.setEnabled(True)
        self.clientEdit = QLineEdit(self.centralwidget)
        self.clientEdit.setObjectName(u"clientEdit")
        self.clientEdit.setGeometry(QRect(90, 20, 261, 21))
        self.clientEdit.setClearButtonEnabled(False)
        self.client = QLabel(self.centralwidget)
        self.client.setObjectName(u"client")
        self.client.setGeometry(QRect(20, 20, 54, 16))
        self.clientbtn = QPushButton(self.centralwidget)
        self.clientbtn.setObjectName(u"clientbtn")
        self.clientbtn.setGeometry(QRect(360, 20, 75, 24))
        self.pathBtn = QPushButton(self.centralwidget)
        self.pathBtn.setObjectName(u"pathBtn")
        self.pathBtn.setGeometry(QRect(360, 50, 75, 24))
        self.path = QLabel(self.centralwidget)
        self.path.setObjectName(u"path")
        self.path.setGeometry(QRect(20, 50, 54, 16))
        self.pathEdit = QLineEdit(self.centralwidget)
        self.pathEdit.setObjectName(u"pathEdit")
        self.pathEdit.setGeometry(QRect(90, 50, 261, 21))
        self.pathEdit.setClearButtonEnabled(False)
        self.defaultTdataEdit = QLineEdit(self.centralwidget)
        self.defaultTdataEdit.setObjectName(u"defaultTdataEdit")
        self.defaultTdataEdit.setGeometry(QRect(90, 80, 261, 21))
        self.defaultTdataEdit.setClearButtonEnabled(False)
        self.defaultTdata = QLabel(self.centralwidget)
        self.defaultTdata.setObjectName(u"defaultTdata")
        self.defaultTdata.setGeometry(QRect(20, 80, 54, 16))
        self.args = QLabel(self.centralwidget)
        self.args.setObjectName(u"args")
        self.args.setGeometry(QRect(20, 110, 54, 16))
        self.argsWidget = QListWidget(self.centralwidget)
        self.argsWidget.setObjectName(u"argsWidget")
        self.argsWidget.setGeometry(QRect(90, 110, 261, 131))
        self.addBtn = QPushButton(self.centralwidget)
        self.addBtn.setObjectName(u"addBtn")
        self.addBtn.setGeometry(QRect(360, 110, 75, 24))
        self.delBtn = QPushButton(self.centralwidget)
        self.delBtn.setObjectName(u"delBtn")
        self.delBtn.setGeometry(QRect(360, 140, 75, 24))
        self.finishBtn = QPushButton(self.centralwidget)
        self.finishBtn.setObjectName(u"finishBtn")
        self.finishBtn.setGeometry(QRect(360, 215, 75, 24))
        setting.setCentralWidget(self.centralwidget)

        self.retranslateUi(setting)

        QMetaObject.connectSlotsByName(setting)
    # setupUi

    def retranslateUi(self, setting):
        setting.setWindowTitle(QCoreApplication.translate("setting", u"\u8bbe\u7f6e", None))
#if QT_CONFIG(tooltip)
        self.clientEdit.setToolTip(QCoreApplication.translate("setting", u"\u5728\u8fd9\u91cc\u8f93\u5165\u4f60\u6240\u4f7f\u7528\u7684Telegram\u5ba2\u6237\u7aef\u540d\u79f0", None))
#endif // QT_CONFIG(tooltip)
        self.clientEdit.setPlaceholderText(QCoreApplication.translate("setting", u"\u8bf7\u8f93\u5165\u5ba2\u6237\u7aef\u7684\u540d\u79f0", None))
        self.client.setText(QCoreApplication.translate("setting", u"\u5ba2\u6237\u7aef", None))
#if QT_CONFIG(tooltip)
        self.clientbtn.setToolTip(QCoreApplication.translate("setting", u"\u81ea\u52a8\u83b7\u53d6\u5ba2\u6237\u7aef\u540d\u79f0", None))
#endif // QT_CONFIG(tooltip)
        self.clientbtn.setText(QCoreApplication.translate("setting", u"\u81ea\u52a8\u83b7\u53d6", None))
#if QT_CONFIG(tooltip)
        self.pathBtn.setToolTip(QCoreApplication.translate("setting", u"\u81ea\u52a8\u83b7\u53d6\u5ba2\u6237\u7aef\u8def\u5f84", None))
#endif // QT_CONFIG(tooltip)
        self.pathBtn.setText(QCoreApplication.translate("setting", u"\u81ea\u52a8\u83b7\u53d6", None))
        self.path.setText(QCoreApplication.translate("setting", u"\u8def\u5f84", None))
#if QT_CONFIG(tooltip)
        self.pathEdit.setToolTip(QCoreApplication.translate("setting", u"\u5728\u8fd9\u91cc\u8f93\u5165\u4f60\u6240\u4f7f\u7528\u7684Telegram\u5ba2\u6237\u7aef\u8def\u5f84", None))
#endif // QT_CONFIG(tooltip)
        self.pathEdit.setPlaceholderText(QCoreApplication.translate("setting", u"\u8bf7\u8f93\u5165\u5ba2\u6237\u7aef\u8def\u5f84", None))
#if QT_CONFIG(tooltip)
        self.defaultTdataEdit.setToolTip(QCoreApplication.translate("setting", u"\u5728\u8fd9\u91cc\u8f93\u5165\u9ed8\u8ba4\u767b\u5f55\u7684\u8d26\u6237\u6807\u7b7e", None))
#endif // QT_CONFIG(tooltip)
        self.defaultTdataEdit.setPlaceholderText(QCoreApplication.translate("setting", u"\u8bf7\u8f93\u5165\u9ed8\u8ba4\u8d26\u6237\u6807\u7b7e", None))
        self.defaultTdata.setText(QCoreApplication.translate("setting", u"\u9ed8\u8ba4tdata", None))
        self.args.setText(QCoreApplication.translate("setting", u"\u53c2\u6570", None))
#if QT_CONFIG(tooltip)
        self.argsWidget.setToolTip(QCoreApplication.translate("setting", u"\u5728\u8fd9\u91cc\u6dfb\u52a0\u5907\u7528\u767b\u5f55\u7684\u8d26\u6237\u6807\u7b7e", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.addBtn.setToolTip(QCoreApplication.translate("setting", u"\u6dfb\u52a0\u53c2\u6570", None))
#endif // QT_CONFIG(tooltip)
        self.addBtn.setText(QCoreApplication.translate("setting", u"\u6dfb\u52a0", None))
#if QT_CONFIG(tooltip)
        self.delBtn.setToolTip(QCoreApplication.translate("setting", u"\u5220\u9664\u53c2\u6570", None))
#endif // QT_CONFIG(tooltip)
        self.delBtn.setText(QCoreApplication.translate("setting", u"\u5220\u9664", None))
#if QT_CONFIG(tooltip)
        self.finishBtn.setToolTip(QCoreApplication.translate("setting", u"\u4fdd\u5b58\u914d\u7f6e", None))
#endif // QT_CONFIG(tooltip)
        self.finishBtn.setText(QCoreApplication.translate("setting", u"\u4fdd\u5b58", None))
    # retranslateUi

