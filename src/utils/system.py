import sys
import traceback

from src.utils.files_utils import restore_file


def handle_global_exception(self, exc_type, exc_value, exc_traceback):
    """捕获全局未处理错误"""
    if exc_type is KeyboardInterrupt:
        self.logger.info("捕捉退出命令.")
        sys.exit(0)
    errorMessage = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    self.logger.critical(f"捕获的未处理异常: \n{errorMessage}")


def ctrl_handler(ctrl_type):
    if ctrl_type == 2:
        restore_file()
        return False
    return True