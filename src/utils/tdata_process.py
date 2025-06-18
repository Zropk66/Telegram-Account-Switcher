import asyncio
import atexit
import os
import subprocess
from datetime import datetime

from src.utils.config_manage import ConfigManage
from src.utils.files_utils import is_exists, account_switch, recovery
from src.utils.logger import Logger
from src.utils.process_utils import safe_exit, check_process_alive
from src.utils.system_utils import format_timedelta



class TdataProcess:
    def __init__(self):
        self.logger = Logger()
        self._config = ConfigManage()

    def process(self):
        tag = self._config.tag
        try:
            if asyncio.run(self.__process(tag)) is False:
                self.logger.error('客户端启动超时.')
                safe_exit()
        except Exception as e:
            self.logger.error(e, exc_info=True)
            safe_exit(restore=True)
        self.logger.info('客户端启动成功, 运行状况持续受到监控.')
        start_time = datetime.now()

        while True:
            alive = check_process_alive(self._config.client)
            if alive is False:
                end_time = datetime.now()
                self.logger.info(f"监控时长：{format_timedelta(end_time - start_time)}")
                break
        safe_exit(restore=True)

    async def __process(self, tag):
        """判断账户是否切换"""
        for i in range(30):
            tags = self._config.tags
            if tag not in tags:
                if is_exists(os.path.join(self._config.path, 'tdata'), self._config.default):
                    self.run_command()
                else:
                    if account_switch('restore'):
                        self.logger.info('账户已切换为默认账户.')
                        self.run_command()
                self.logger.info('客户端已启动.')
                safe_exit()
            atexit.register(recovery)
            startup_successful = False
            if is_exists(os.path.join(self._config.path, 'tdata'), tag):
                startup_successful = self.run_command()
            else:
                if account_switch('switch'):
                    self.logger.info(f"已切换为目标账户 -> '{tag}'.")
                    startup_successful = self.run_command()
                else:
                    safe_exit(restore=True)
            return startup_successful
        return False

    def run_command(self):
        """启动目标程序"""
        client_path = os.path.join(self._config.path, self._config.client)
        try:
            subprocess.Popen(
                [str(client_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                shell=True,
                start_new_session=True
            )
            while True:
                alive = check_process_alive(self._config.client)
                if alive:
                    break
            return True
        except FileNotFoundError:
            self.logger.error(f"客户端路径不存在: {client_path}")
        except Exception as e:
            self.logger.error(f"启动异常: {str(e)}")
        return False
