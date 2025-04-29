# -*- coding: utf-8 -*-
# @Time : 2025/1/2 13:12
# @Author : DecadeX
import atexit
import ctypes
import json
import logging
import os
import os.path
import random
import socket
import subprocess
import sys
import time
import traceback
from typing import NoReturn

import psutil
from PySide6.QtCore import QObject, QEvent, Qt, QRunnable, QThreadPool
from PySide6.QtWidgets import QMainWindow, QApplication, QMessageBox, QFileDialog, QListWidgetItem

from ui_settings import Ui_setting

TITLE = 'TAS'
VERSION = '1.0'
WORK_PATH = os.getcwd()


def check_singleton(port):
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        lock_socket.bind(('0.0.0.0', port))
        lock_socket.listen()
        return lock_socket
    except socket.error:
        return False


lock = check_singleton(9564)


class Main:
    def __init__(self):
        self.__version__ = 1.0
        self.logger = logging.getLogger(__name__)
        self.startHiddenProcess = lambda exe_path: psutil.Popen(
            exe_path,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        )

        self.client = 'Telegram.exe'
        self.path = ''
        self.default = ''
        self.args = []
        self.arg = ''

    def set_value(self, name: str, value):
        """设置全局变量"""
        try:
            if name == 'client':
                self.client = value
            if name == 'path':
                self.path = value
            if name == 'default':
                self.default = value
            if name == 'args':
                self.args = list(value)
            if name == 'arg':
                self.arg = value
                return
            self.config_helper(field=name, mode='w', value=value)
        except Exception as e:
            self.logger.error(f'{name} 设置失败.')
            self.logger.critical(e)

    def config_helper(self, field: str, mode: str, value=None):
        """配置管理器"""
        try:
            supportKey = {'client': self.client, 'path': '', 'args': [], 'default': ''}
            supportMode = {'w', 'r'}

            if field == 'defaultMain':
                field = 'default'
            if mode not in supportMode:
                raise ValueError(f"不支持的模式： {mode}，仅支持 'r' 或 'w' 模式")

            if field not in supportKey.keys():
                raise ValueError(f"不支持的字段: {field}")

            configPath = os.path.join(WORK_PATH, "configs.json")
            if not os.path.exists(configPath):
                with open(configPath, 'w', encoding='utf-8') as f:
                    f.write('')

            configs = {}
            if os.path.exists(configPath):
                try:
                    with open(configPath, 'r', encoding='utf-8') as f:
                        data = f.read()
                        if not (data is None) or not data == '':
                            configs = json.loads(data)
                except (json.JSONDecodeError, json.decoder.JSONDecodeError):
                    self.logger.error('配置文件损坏.')
                except Exception as e:
                    raise IOError(f"配置读取失败: {str(e)}") from e
            else:
                self.logger.info('配置文件不存在.')

            configs = {k: v for k, v in configs.items() if k in supportKey.keys()}

            if mode == 'r':
                for k, v in configs.items():
                    if k == field:
                        if not (value is None) or not value == '':
                            return v
                configs[field] = supportKey.get(field)

                with open(configPath, 'w', encoding='utf-8') as f:
                    json.dump(configs, f, indent=4)
                return configs.get(field)

            try:
                if not isinstance(configs[field], list) and field == 'args':
                    configs[field] = []
                elif field == 'args' and value != '':
                    for arg in value:
                        if arg not in configs[field]:
                            configs[field].append(arg)
                else:
                    configs[field] = value
                if value != '' or value == []:
                    with open(configPath, 'w', encoding='utf-8') as f:
                        json.dump(configs, f, indent=4)
                return None
            except Exception as e:
                raise IOError(f"写入配置失败: {str(e)}") from e
        except Exception as e:
            self.logger.error('文件操作出现未知错误.')
            self.logger.critical(e)
            return None

    def is_exists(self, base_path: str, target_file: str):
        """判断文件夹中是否存在目标文件"""
        try:
            if os.path.exists(os.path.join(base_path, target_file)):
                return True
            else:
                return False
        except (FileNotFoundError, PermissionError, TypeError) as e:
            self.logger.error(e)
            return False

    def is_in_directories(self, base_path: str, target_file: str):
        """检测文件夹中是否存在指定文件"""
        if not os.path.isdir(base_path):
            self.logger.error(f"{base_path} 不是一个有效路径.")
            return ''

        for entry in os.scandir(base_path):
            if entry.is_dir():
                filePath = os.path.join(entry.path, target_file)
                if os.path.isfile(filePath):
                    return entry.name
        return ''

    def set_logger(self):
        """设置日志记录器"""

        class PopupHandler(logging.Handler):
            def emit(self, record):
                """处理日志记录并弹出窗口"""
                try:
                    if isinstance(record.msg, BaseException):
                        message = f"捕获的未处理异常:\n{self.format_exception(record.msg)}"
                    else:
                        message = record.msg

                    supportLevels = [logging.WARNING, logging.CRITICAL]
                    if record.levelno in supportLevels:
                        self.show_message(message, record)
                except (AttributeError, TypeError, Exception):
                    self.handleError(record)

            @staticmethod
            def show_message(message, level):
                """显示弹窗"""
                app = QApplication.instance() or QApplication(sys.argv)
                level_map = {
                    logging.WARNING: QMessageBox.Warning,
                    logging.CRITICAL: QMessageBox.Critical,
                }

                if isinstance(level, logging.LogRecord):
                    level_no = level.levelno
                    level_name = level.levelname
                elif isinstance(level, int):
                    level_no = level
                    level_name = logging.getLevelName(level)
                elif isinstance(level, str):
                    level_no = getattr(logging, level.upper(), logging.INFO)
                    level_name = level.upper()
                else:
                    level_no = logging.INFO
                    level_name = "INFO"

                icon = level_map.get(level_no, QMessageBox.Information)

                msgBox = QMessageBox()
                msgBox.setWindowTitle(level_name)
                msgBox.setText(message)
                msgBox.setIcon(icon)
                msgBox.exec()

            @staticmethod
            def format_exception(exception):
                """格式化异常为字符串"""
                return "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

        self.logger.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler(os.path.join(WORK_PATH, "TAS_log.txt"), mode="a", encoding="utf-8",
                                           delay=False)
        file_handler.setLevel(logging.DEBUG)
        file_handler.flush = file_handler.stream.flush

        popup_handler = PopupHandler()

        popup_handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        popup_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(popup_handler)

        self.logger.propagate = False

    def tdata_process(self):
        """判断 tdata 状态并执行相关操作"""

        def run_command():
            command = f'start "" "{os.path.join(self.path, self.client)}"'
            return subprocess.Popen(command, shell=True, cwd=self.path)

        def not_arg():
            if self.is_exists(os.path.join(self.path, 'tdata'), self.default):
                run_command()
                self.logger.info('客户端启动.')
            else:
                if self.modify_file('restore'):
                    run_command()
                    self.logger.info('客户端启动.')
            self.system_exit()

        def has_arg() -> bool:
            atexit.register(self.restore_file)
            startupSuccessful = False
            if self.is_exists(os.path.join(self.path, 'tdata'), self.arg):
                run_command()
                startupSuccessful = True
                self.logger.info('无需切换账户.')
            else:
                if self.modify_file('modify'):
                    run_command()
                    startupSuccessful = True
                else:
                    print(114514)
                    self.system_exit(restore=True)
            return startupSuccessful

        try:
            if not self.arg:
                not_arg()
                return

            while True:
                if has_arg():
                    self.logger.info('客户运行状况持续受到监控.')
                    break
            isRunning = True
            while isRunning:
                time.sleep(1)
                isRunning = self.handle_process(client=self.client, mode='isRun')
            self.logger.info('客户端已关闭.')
            self.system_exit(restore=True)
        except Exception:
            self.logger.error('参数解析失败.')
            self.system_exit(restore=True)

    def handle_global_exception(self, exc_type, exc_value, exc_traceback):
        """捕获全局未处理错误"""
        if exc_type is KeyboardInterrupt:
            self.logger.info("捕捉退出命令.")
            sys.exit(0)
        errorMessage = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        self.logger.critical(f"捕获的未处理异常: \n{errorMessage}")

    def restore_file(self):
        """程序结束时自动还原"""
        try:
            self.handle_process(mode='kill')
            time.sleep(1)
            self.modify_file('restore')
        except (FileNotFoundError, PermissionError):
            self.logger.error('恢复帐户时出现错误.')

    def ctrl_handler(self, ctrl_type):
        if ctrl_type == 2:
            self.restore_file()
            return False
        return True

    def system_exit(self, message=None, restore=False) -> NoReturn:
        """退出程序"""
        self.handle_process(mode='kill')
        if restore:
            self.modify_file('restore')
        self.logger.info('程序结束.')
        atexit.unregister(self.restore_file)
        open(os.path.join(WORK_PATH, "TAS_log.txt"), 'a', encoding='utf-8').write(
            '----------------------------------------\n')
        lock.close()
        raise SystemExit(message)

    def handle_process(self, client=None, mode: str = 'isRun'):
        """程序进程相关函数，能判断程序是否运行，是否结束程序，返回程序路径"""
        client_is_list = False
        find_client = False
        if client is None:
            client = self.client
        if isinstance(client, list):
            client_is_list = True

        black_list = ['sogouimebroker', 'runtimebroker', 'ChsIME']

        for process in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                processName = process.info['name']
                if client_is_list:
                    if any(keyword.lower() in processName.lower() for keyword in black_list):
                        continue
                    if any(keyword.lower() in processName.lower() for keyword in client):
                        find_client = True
                else:
                    if processName == client:
                        find_client = True
                if find_client:
                    if mode == 'path':
                        return os.path.dirname(process.info['exe'])
                    elif mode == 'kill':
                        try:
                            process.terminate()
                            return True
                        except Exception:
                            self.logger.error(f"'无法结束进程 '{process.info['name']}'.'")
                            return False
                    elif mode == 'isRun':
                        return True
                    elif mode == 'check':
                        return processName
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                self.logger.error(f'进程操作出现错误.')

        return False

    def modify_file(self, mode: str, retries=0, max_retries=3):
        """修改tdata文件，实现不同账号登录"""
        if retries >= max_retries:
            # self.modifyFile('restore')
            self.system_exit()
        random_str = ''.join(random.sample('ABCDEFG', 5))
        temp = f'tdata-{random_str}'
        try:
            if mode == 'restore':
                try:
                    os.rename(os.path.join(self.path, 'tdata'), os.path.join(self.path, temp))
                except FileNotFoundError:
                    pass
                os.rename(
                    os.path.join(self.path, self.is_in_directories(self.path, self.default)),
                    os.path.join(self.path, 'tdata'))
                self.logger.info('恢复账户.')
                return True
            elif mode == 'modify':
                try:
                    arg_dir = os.path.join(self.path, self.is_in_directories(self.path, self.arg))
                except TypeError:
                    return True
                try:
                    os.rename(os.path.join(self.path, 'tdata'), os.path.join(self.path, temp))
                except FileNotFoundError:
                    pass
                os.rename(arg_dir, os.path.join(self.path, 'tdata'))
                self.logger.info('账户切换.')
                return True
            self.logger.error(f"模式 '{mode}' 无法执行，文件状态不符合要求.")
            return False
        except (FileNotFoundError, PermissionError) as e:
            self.logger.error(f"文件操作失败: {e}, 重试... ({retries + 1}/{max_retries})")
            time.sleep(1)
            return self.modify_file(mode, retries + 1, max_retries)

    def check_client(self):
        """检查客户端是否正确"""
        client = self.config_helper(field='client', mode='r')
        path = self.config_helper(field='path', mode='r')
        if os.path.isfile(os.path.join(path, client)):
            return client
        self.logger.warning('无法找到客户端.')
        self.start_setting_window()
        sys.exit()

    def check_path(self):
        """检查路径是否正确"""
        path = self.config_helper(field='path', mode='r')
        if os.path.isdir(path):
            return path
        self.logger.warning('路径格式不正确.')
        self.start_setting_window()
        sys.exit()

    def check_default_tdata(self):
        """获取默认登录账户"""
        default_tdata = str(self.config_helper(field='default', mode='r'))
        if default_tdata is None or default_tdata == '':
            self.config_helper(field='default', mode='w', value='')
            self.logger.warning('未设置默认 Tdata.')
            self.start_setting_window()
            sys.exit()
        if not self.is_in_directories(self.path, default_tdata):
            self.logger.warning(
                f"默认帐户配置无效, 未找到标签为 '{default_tdata}' 的帐户文件夹"
            )
            self.start_setting_window()
            sys.exit()

        return default_tdata

    def check_arg(self):
        """处理参数"""
        tdatas = self.config_helper(field='args', mode='r')
        try:
            argument = ''
            if len(sys.argv) <= 3:
                try:
                    argument = sys.argv[1].split('--')[1]
                except IndexError:
                    self.logger.info('参数解析错误，参数将被丢弃.')
                    return ''

                if argument.lower() == 'help':
                    self.logger.warning("--help -> 帮助文档\n--setting -> 打开设置\n--login -> 登录指定标签的账号")
                    sys.exit()
                elif argument.lower() == 'setting':
                    self.logger.info('打开设置.')
                    self.start_setting_window()
                    sys.exit()
                elif argument.lower() == 'login':
                    argument = sys.argv[-1]
                    if argument is None or argument == '' or argument == '--login':
                        return ''
                    if argument not in tdatas:
                        if argument == self.config_helper(field='default', mode='r'):
                            return ''
                        self.logger.warning(
                            f"参数 '{argument}' 尚未注册.\n"
                            f"您可以使用 '-setting' 参数打开设置来添加它.")
                        self.system_exit()
                    if not self.is_in_directories(self.path, argument):
                        self.logger.warning(f"无法找到标签为 '{argument}'")
                        return ''
                    return argument
            else:
                self.logger.warning(f"参数不正确.")
            self.logger.info(f"未知参数 '{argument}'.")
            return ''
        except ValueError as e:
            self.logger.critical("".join(traceback.format_exception(type(e), e, e.__traceback__)))
            self.system_exit()

    def initialize(self):
        """初始化函数"""
        sys.excepthook = self.handle_global_exception
        kernel32 = ctypes.WinDLL("kernel32")
        HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
        handleCtrl = HandlerRoutine(self.ctrl_handler)
        kernel32.SetConsoleCtrlHandler(handleCtrl, True)
        self.set_logger()
        if lock is False:
            self.logger.warning('当前已有实例正在运行.')
            sys.exit()
        if not os.path.exists('configs.json'):
            self.start_setting_window()
        else:
            try:
                self.set_value('client', self.check_client())
                self.set_value('path', self.check_path())
                self.set_value('default', self.check_default_tdata())
                self.set_value('args', self.config_helper(field='args', mode='r'))
                self.set_value('arg', self.check_arg())
            except Exception as e:
                self.logger.error('客户端初始化失败, 请检查设置是否正确.')
                self.logger.critical(e)
                self.start_setting_window()
        self.logger.info('初始化成功.')

    class MainWindow(QMainWindow):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.ui = Ui_setting()
            self.ui.setupUi(self)
            self.main_class = Main()
            self.threadPool = QThreadPool.globalInstance()
            self.ui.clientEdit.setText(self.main_class.config_helper(field='client', mode='r'))
            self.ui.pathEdit.setText(self.main_class.config_helper(field='path', mode='r'))
            self.ui.defaultTdataEdit.setText(self.main_class.config_helper(field='default', mode='r'))
            self.ui.argsWidget.addItems(self.main_class.config_helper(field='args', mode='r'))

            for i in range(self.ui.argsWidget.count()):
                item = self.ui.argsWidget.item(i)
                item.setFlags(item.flags() | Qt.ItemIsEditable)

            self.client_edit_double_click_filter = self.DoubleClickFilter(self.client_edit_double_click_event)
            self.ui.clientEdit.installEventFilter(self.client_edit_double_click_filter)
            self.ui.clientbtn.clicked.connect(self.get_client)

            self.path_edit_double_click_filter = self.DoubleClickFilter(self.path_edit_double_click_event)
            self.ui.pathEdit.installEventFilter(self.path_edit_double_click_filter)
            self.ui.pathBtn.clicked.connect(self.get_path)

            self.ui.addBtn.clicked.connect(self.add_item)
            self.ui.delBtn.clicked.connect(self.del_item)
            self.ui.argsWidget.itemDoubleClicked.connect(self.edit_item)

            self.ui.finishBtn.clicked.connect(self.finish)

        class Worker(QRunnable):
            def __init__(self, fun):
                super().__init__()
                self.fun = fun

            def run(self):
                self.fun()

        def get_path(self):
            worker = self.Worker(self.path_auto_get)
            self.threadPool.start(worker)

        def get_client(self):
            worker = self.Worker(self.client_auto_get)
            self.threadPool.start(worker)

        def path_auto_get(self):
            """自动获取路径"""
            if self.main_class.client is None or self.main_class.client == '':
                self.main_class.logger.warning('客户端名称未设置，请先获取客户端名称后重试.')
            try:
                subprocess.Popen('start "" "tg:"', shell=True)
            except Exception as e:
                self.main_class.logger.error(e)
            client_is_run = False
            for i in range(10):
                if self.main_class.handle_process(mode='isRun'):
                    client_is_run = True
                    break
                time.sleep(1)
            if not client_is_run:
                self.main_class.logger.warning("无法获取到路径，您使用的telegram可能不在我们的预设池里，请手动设置.")
                return ''
            effective_path = ''
            for i in range(5):
                try:
                    effective_path = self.main_class.handle_process(mode='path')
                    if isinstance(effective_path, str) and os.path.isfile(
                            os.path.join(effective_path, self.main_class.client)):
                        self.main_class.handle_process(mode='kill')
                        break
                except Exception as e:
                    self.main_class.logger.error(f"路径检测失败，错误: {e}")
                time.sleep(1)

            if effective_path is None or not isinstance(effective_path, str) or not os.path.isdir(effective_path):
                raise ValueError(f"无效路径: {effective_path}")
            self.main_class.config_helper(field='path', mode='w', value=effective_path)

            self.main_class.logger.info(f"工作路径 -> {effective_path}")
            self.ui.pathEdit.setText(effective_path)

        def client_auto_get(self):
            """自动获取客户端"""
            subprocess.Popen('start "" "tg:"', shell=True)
            time.sleep(5)

            client_map = [
                'iMe',
                'telegram',
                'Forkgram',
                '64Gram',
                'Unigram',
                'Beeper',
                'AyuGram'
            ]

            client = self.main_class.handle_process(client=client_map, mode='check')
            if client != '' and isinstance(client, str):
                self.main_class.logger.info(f"有效客户端 -> {client}")
                self.ui.clientEdit.setText(str(client))
                self.main_class.client = client
                self.main_class.handle_process(mode='kill')
            else:
                self.main_class.logger.warning('无效客户端')
                self.ui.clientEdit.setText('')

        def finish(self):
            """保存所有设置"""
            c = {
                'client': self.ui.clientEdit.text(),
                'path': self.ui.pathEdit.text(),
                'default': self.ui.defaultTdataEdit.text(),
                'args': [self.ui.argsWidget.item(i).text() for i in range(self.ui.argsWidget.count())]
            }
            json.dumps(c, indent=4)
            with open('configs.json', 'w') as f:
                json.dump(c, f, indent=4)
            QMessageBox.information(None, '提示', '设置保存成功.')

        def add_item(self):
            item = QListWidgetItem("New argument")
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.ui.argsWidget.addItem(item)
            self.ui.argsWidget.editItem(item)

        def del_item(self):
            selected_item = self.ui.argsWidget.currentItem()
            if selected_item:
                row = self.ui.argsWidget.row(selected_item)
                self.ui.argsWidget.takeItem(row)

        def edit_item(self, item):
            """当用户双击某个项时，进入编辑模式"""
            self.ui.argsWidget.editItem(item)

        def client_edit_double_click_event(self):
            """客户端选择事件"""
            userSelect, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "客户端主程序 (*.exe)")
            if userSelect:
                client = os.path.basename(userSelect)
                path = os.path.dirname(userSelect)
                self.ui.clientEdit.setText(client)
                self.ui.pathEdit.setText(path)

        def path_edit_double_click_event(self):
            """路径选择事件"""
            path = QFileDialog.getExistingDirectory(self, "选择客户端路径", "")
            if path:
                self.ui.pathEdit.setText(path)

        class DoubleClickFilter(QObject):
            def __init__(self, fun):
                super().__init__()
                self.fun = fun

            def eventFilter(self, obj, event):
                if event.type() == QEvent.MouseButtonDblClick:
                    self.fun()
                    return True
                return super().eventFilter(obj, event)

    def start_setting_window(self):
        """打开设置窗口"""
        app = QApplication.instance() or QApplication(sys.argv)
        widget = self.MainWindow()
        widget.show()
        sys.exit(app.exec())

    def main(self):
        """主函数"""
        self.initialize()
        self.handle_process(mode='kill')
        atexit.register(self.restore_file)
        self.tdata_process()
        atexit.unregister(self.restore_file)
        self.logger.info('程序运行结束.')


if __name__ == '__main__':
    Main().main()
