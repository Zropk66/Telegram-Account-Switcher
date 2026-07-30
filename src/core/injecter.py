"""hook 注入器"""

import argparse
import ctypes
import os
import sys
import time
from ctypes import wintypes

from src.core.logger import Logger

# ---------------------------------------------------------------------
# Windows API 声明
# ---------------------------------------------------------------------

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]

class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]

# 常量
CREATE_SUSPENDED = 0x00000004
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NEW_CONSOLE = 0x00000010
MEM_COMMIT = 0x00001000
MEM_RESERVE = 0x00002000
MEM_RELEASE = 0x00008000
PAGE_READWRITE = 0x00000004
WAIT_TIMEOUT = 0x00000102

# 函数原型
kernel32.CreateProcessW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
    wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
    ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION)
]
kernel32.CreateProcessW.restype = wintypes.BOOL

kernel32.VirtualAllocEx.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD
]
kernel32.VirtualAllocEx.restype = ctypes.c_void_p

kernel32.VirtualFreeEx.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD
]
kernel32.VirtualFreeEx.restype = wintypes.BOOL

kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t)
]
kernel32.WriteProcessMemory.restype = wintypes.BOOL

kernel32.GetProcAddress.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]
kernel32.GetProcAddress.restype = ctypes.c_void_p

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

kernel32.CreateRemoteThread.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
    ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
]
kernel32.CreateRemoteThread.restype = wintypes.HANDLE

kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD

kernel32.GetExitCodeThread.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeThread.restype = wintypes.BOOL

kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
kernel32.ResumeThread.restype = wintypes.DWORD

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.GetLastError.restype = wintypes.DWORD


# ---------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------

def get_loadlibrary_address():
    """
    获取 LoadLibraryW 在目标进程中的地址。
    kernel32.dll 作为 KnownDLL 在系统启动时加载，基地址在所有 64 位进程中一致，
    因此可直接用本进程地址。
    """
    h_kernel32 = kernel32.GetModuleHandleW("kernel32.dll")
    if not h_kernel32:
        raise OSError(f"GetModuleHandleW(kernel32) failed: {kernel32.GetLastError()}")
    addr = kernel32.GetProcAddress(h_kernel32, b"LoadLibraryW")
    if not addr:
        raise OSError(f"GetProcAddress(LoadLibraryW) failed: {kernel32.GetLastError()}")
    return addr


def write_environment_block(env_dict):
    """
    将环境变量字典编码为 CREATE_UNICODE_ENVIRONMENT 格式的环境块。
    格式: key=value\\0key=value\\0...\\0\\0 (UTF-16LE)
    """
    parts = []
    for k, v in env_dict.items():
        parts.append(f"{k}={v}")
    block = "\0".join(parts) + "\0\0"
    return block.encode("utf-16-le")


# ---------------------------------------------------------------------
# 注入核心
# ---------------------------------------------------------------------

def inject_dll(h_process, dll_path, logger: Logger):
    """向目标进程注入 DLL，返回是否成功。"""
    dll_path_abs = os.path.abspath(dll_path)
    if not os.path.isfile(dll_path_abs):
        raise FileNotFoundError(f"DLL not found: {dll_path_abs}")

    dll_path_w = dll_path_abs.replace("/", "\\")
    dll_bytes = dll_path_w.encode("utf-16-le") + b"\x00\x00"
    alloc_size = len(dll_bytes)

    logger.debug(f"在目标进程分配 {alloc_size} 字节内存...")
    remote_mem = kernel32.VirtualAllocEx(
        h_process, None, alloc_size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE
    )
    if not remote_mem:
        raise OSError(f"VirtualAllocEx failed: {kernel32.GetLastError()}")
    logger.debug(f"远程内存地址: 0x{remote_mem:016X}")

    written = ctypes.c_size_t(0)
    if not kernel32.WriteProcessMemory(h_process, remote_mem, dll_bytes, alloc_size, ctypes.byref(written)):
        raise OSError(f"WriteProcessMemory failed: {kernel32.GetLastError()}")
    logger.debug(f"已写入 {written.value} 字节 (DLL 路径)")

    load_lib = get_loadlibrary_address()
    logger.debug(f"LoadLibraryW @ 0x{load_lib:016X}")

    thread_id = wintypes.DWORD(0)
    logger.debug("创建远程线程 (LoadLibraryW)...")
    h_thread = kernel32.CreateRemoteThread(
        h_process, None, 0, load_lib, remote_mem, 0, ctypes.byref(thread_id)
    )
    if not h_thread:
        raise OSError(f"CreateRemoteThread failed: {kernel32.GetLastError()}")
    logger.debug(f"远程线程已创建 (TID={thread_id.value})")

    logger.debug("等待 LoadLibraryW 执行完成...")
    result = kernel32.WaitForSingleObject(h_thread, 10000)
    if result == 0xFFFFFFFF or result == WAIT_TIMEOUT:
        kernel32.CloseHandle(h_thread)
        raise OSError(f"WaitForSingleObject failed/timeout: result={result}")

    exit_code = wintypes.DWORD(0)
    kernel32.GetExitCodeThread(h_thread, ctypes.byref(exit_code))

    kernel32.CloseHandle(h_thread)
    kernel32.VirtualFreeEx(h_process, remote_mem, 0, MEM_RELEASE)
    logger.debug("远程内存已释放")

    if exit_code.value == 0:
        raise OSError("LoadLibraryW returned NULL (DLL load failed in target process)")

    logger.debug(f"LoadLibraryW 返回模块句柄 0x{exit_code.value:016X}")
    return True


# ---------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------

def launch_with_hook(
    telegram_path: str,
    dll_path: str,
    logger: Logger,
    tdata_name: str | None = None,
    workdir: str | None = None,
    extra_args: str = "",
    no_suspend: bool = False,
) -> int | None:
    """
    以挂起方式启动 Telegram 并注入 hook.dll，返回进程 PID（失败返回 None）。

    参数:
        telegram_path   Telegram.exe 路径 (必需)
        dll_path        hook.dll 路径 (必需)
        logger          日志记录器 (必需)
        tdata_name      自定义 tdata 目录名，如 tdata-1
        workdir         传给 Telegram 的工作目录 (-workdir 参数)
        extra_args      额外传给 Telegram 的命令行参数
        no_suspend      不挂起直接注入 (不推荐，hook 时机不保证)
    """
    telegram_path = os.path.abspath(telegram_path)
    if not os.path.isfile(telegram_path):
        logger.error(f"找不到 Telegram: {telegram_path}")
        return None

    dll_path = os.path.abspath(dll_path)
    if not os.path.isfile(dll_path):
        logger.error(f"找不到 DLL: {dll_path}")
        return None

    logger.debug(f"Telegram : {telegram_path}")
    logger.debug(f"DLL      : {dll_path}")
    if tdata_name:
        logger.debug(f"tdata名  : {tdata_name}")

    env = dict(os.environ)
    if tdata_name:
        env["TDATA_NAME"] = tdata_name

    cmd_line = f'"{telegram_path}"'
    if workdir:
        workdir_abs = os.path.abspath(workdir)
        cmd_line += f' -workdir "{workdir_abs}"'
    if extra_args:
        cmd_line += f" {extra_args}"

    creation_flags = CREATE_UNICODE_ENVIRONMENT | CREATE_NEW_CONSOLE
    if not no_suspend:
        creation_flags |= CREATE_SUSPENDED

    si = STARTUPINFOW()
    si.cb = ctypes.sizeof(STARTUPINFOW)
    si.dwFlags = 0
    si.wShowWindow = 1
    pi = PROCESS_INFORMATION()

    env_block = write_environment_block(env)

    logger.debug(f"启动命令行: {cmd_line}")
    logger.debug(f"挂起模式  : {'否' if no_suspend else '是'}")

    workdir_for_process = os.path.dirname(telegram_path)

    success = kernel32.CreateProcessW(
        None,
        ctypes.create_unicode_buffer(cmd_line),
        None, None, False,
        creation_flags, env_block, workdir_for_process,
        ctypes.byref(si), ctypes.byref(pi)
    )
    if not success:
        logger.error(f"CreateProcessW 失败: {kernel32.GetLastError()}")
        return None

    logger.info(f"进程已创建 PID={pi.dwProcessId}")

    if not no_suspend:
        try:
            logger.debug("进程处于挂起状态，开始注入...")
            inject_dll(pi.hProcess, dll_path, logger)
            logger.info("DLL 注入成功")
        except Exception as e:
            logger.error(f"注入失败: {e}")
            logger.debug("终止挂起的进程...")
            kernel32.ResumeThread(pi.hThread)
            kernel32.CloseHandle(pi.hThread)
            kernel32.CloseHandle(pi.hProcess)
            return None

        logger.debug("恢复主线程执行...")
        prev = kernel32.ResumeThread(pi.hThread)
        logger.debug(f"主线程已恢复 (prev suspend count={prev})")
    else:
        logger.debug("非挂起模式，等待进程初始化后注入...")
        time.sleep(0.3)
        try:
            inject_dll(pi.hProcess, dll_path, logger)
            logger.info("DLL 注入成功")
        except Exception as e:
            logger.error(f"注入失败: {e}")
            kernel32.CloseHandle(pi.hThread)
            kernel32.CloseHandle(pi.hProcess)
            return None

    logger.info(f"Telegram 已启动 (PID={pi.dwProcessId})")
    if tdata_name:
        logger.info(f"已将 tdata 重定向为: {tdata_name}")

    kernel32.CloseHandle(pi.hThread)
    kernel32.CloseHandle(pi.hProcess)
    return pi.dwProcessId


def main():
    parser = argparse.ArgumentParser(
        description="hook DLL 注入器 - 挂起启动 Telegram 并注入 DLL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("telegram", help="Telegram.exe 路径")
    parser.add_argument("--dll", default=None, help="hook.dll 路径 (默认与脚本同目录)")
    parser.add_argument("--tdata", default=None, help="自定义 tdata 目录名，如 tdata-1")
    parser.add_argument("--workdir", default=None, help="传给 Telegram 的工作目录 (-workdir)")
    parser.add_argument("--args", default="", help="额外传给 Telegram 的命令行参数")
    parser.add_argument("--no-suspend", action="store_true", help="不挂起直接注入 (不推荐)")
    opts = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    dll_path = opts.dll or os.path.join(script_dir, "hook.dll")

    pid = launch_with_hook(
        telegram_path=opts.telegram,
        dll_path=dll_path,
        logger=Logger(),
        tdata_name=opts.tdata,
        workdir=opts.workdir,
        extra_args=opts.args,
        no_suspend=opts.no_suspend,
    )
    return 0 if pid is not None else 1


if __name__ == "__main__":
    sys.exit(main())
