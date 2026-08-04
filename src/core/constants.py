"""系统全局常量与配置默认值定义."""

from enum import Enum

# --- 应用元数据 ---
APP_TITLE = "TAS"
APP_VERSION = "2.1.0"
SINGLE_INSTANCE_LOCK_NAME = "TelegramAccountSwitcher"
MUTEX_PREFIX = "Global\\"


class LaunchMode(Enum):
    """账户切换启动模式."""

    HOOK = "hook"
    SYMLINK = "symlink"


# --- 文件与目录名称 ---
CONFIG_FILE = "config.json"
TDATA_DIR = "tdata"
IDENTITY_FOLDER = "D877F783D5D3EF8Cs"
INFO_SUBFOLDER = "maps"
KEY_FOLDER = "key_datas"
TAG_FILE = "tas_tag"
TEMP_FILE_SUFFIX = ".tmp"

# --- Telegram 内部常数 ---
TELEGRAM_EXE = "Telegram.exe"
TELEGRAM_IDENTITY_KEY = "D877F783D5D3EF8C"
TELEGRAM_CONFIGS_SUBPATH = "configs"
DEFAULT_DATANAME = "data"
TELEGRAM_REG_KEY = r"tg\shell\open\command"

# --- 进程与监控设置 ---
MAX_RETRIES = 30
MONITOR_MTIME_CHECK_INTERVAL = 2.0
MONITOR_SESSION_MIN_DURATION = 60.0

# --- IPC 通信常数 ---
IPC_PIPE_ADDRESS = r"\\.\pipe\TAS_IPC_PIPE"
IPC_AUTH_KEY = b"TAS_IPC_SECRET"

# --- 密码学常数与不变量 ---
GCM_MARKER = b"\x47\x43\x4d"
NONCE_SIZE = 12
TAG_SIZE = 16
LOCAL_ITER_NO_PWD = 4
LOCAL_ITER_WITH_PWD = 400
STRONG_ITER_COUNT = 100000
TDF_MAGIC = b"TDF$"
