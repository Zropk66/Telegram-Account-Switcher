"""Hook 注入器."""

import argparse
import ctypes
import os
import sys
import time
from ctypes import wintypes

from src.core.logger import Logger

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


CREATE_SUSPENDED = 0x00000004
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NEW_CONSOLE = 0x00000010
MEM_COMMIT = 0x00001000
MEM_RESERVE = 0x00002000
MEM_RELEASE = 0x00008000
PAGE_READWRITE = 0x00000004
WAIT_TIMEOUT = 0x00000102

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

kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL

kernel32.GetLastError.restype = wintypes.DWORD


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
        ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_void_p),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9

kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
kernel32.CreateJobObjectW.restype = wintypes.HANDLE

kernel32.SetInformationJobObject.argtypes = [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
]
kernel32.SetInformationJobObject.restype = wintypes.BOOL

kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL

_job_handle: int | None = None


def _assign_to_job(h_process: int, logger: Logger) -> None:
    """将进程分配到 Job Object."""
    global _job_handle
    if _job_handle is None:
        _job_handle = kernel32.CreateJobObjectW(None, None)
        if not _job_handle:
            logger.debug(f"CreateJobObjectW 失败: {kernel32.GetLastError()}")
            return
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
                _job_handle, JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info),
        ):
            logger.debug(f"SetInformationJobObject 失败: {kernel32.GetLastError()}")
            _job_handle = None
            return
        logger.debug(f"Job Object 已创建: handle=0x{_job_handle:016X}")

    if not kernel32.AssignProcessToJobObject(_job_handle, h_process):
        logger.debug(f"AssignProcessToJobObject 失败: {kernel32.GetLastError()}")


def get_loadlibrary_address() -> int:
    """获取 LoadLibraryW 在目标进程中的地址."""
    h_kernel32 = kernel32.GetModuleHandleW("kernel32.dll")
    if not h_kernel32:
        raise OSError(f"GetModuleHandleW(kernel32) failed: {kernel32.GetLastError()}")
    addr = kernel32.GetProcAddress(h_kernel32, b"LoadLibraryW")
    if not addr:
        raise OSError(f"GetProcAddress(LoadLibraryW) failed: {kernel32.GetLastError()}")
    return addr


def write_environment_block(env_dict: dict) -> bytes:
    """将环境变量字典编码为环境块数据."""
    parts = []
    for k, v in env_dict.items():
        parts.append(f"{k}={v}")
    block = "\0".join(parts) + "\0\0"
    return block.encode("utf-16-le")


def inject_dll(h_process: int, dll_path: str, logger: Logger) -> bool:
    """向目标进程注入 DLL."""
    dll_path_abs = os.path.abspath(dll_path)
    if not os.path.isfile(dll_path_abs):
        raise FileNotFoundError(f"DLL 未找到: {dll_path_abs}")

    dll_path_w = dll_path_abs.replace("/", "\\")
    dll_bytes = dll_path_w.encode("utf-16-le") + b"\x00\x00"
    alloc_size = len(dll_bytes)

    logger.debug(f"在目标进程分配 {alloc_size} 字节内存...")
    remote_mem = kernel32.VirtualAllocEx(
        h_process, None, alloc_size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE
    )
    if not remote_mem:
        raise OSError(f"VirtualAllocEx failed: {kernel32.GetLastError()}")

    written = ctypes.c_size_t(0)
    if not kernel32.WriteProcessMemory(h_process, remote_mem, dll_bytes, alloc_size, ctypes.byref(written)):
        raise OSError(f"WriteProcessMemory failed: {kernel32.GetLastError()}")

    load_lib = get_loadlibrary_address()

    thread_id = wintypes.DWORD(0)
    h_thread = kernel32.CreateRemoteThread(
        h_process, None, 0, load_lib, remote_mem, 0, ctypes.byref(thread_id)
    )
    if not h_thread:
        raise OSError(f"CreateRemoteThread failed: {kernel32.GetLastError()}")
    logger.debug(f"远程线程已创建: TID={thread_id.value}, LoadLibraryW=0x{load_lib:016X}")

    result = kernel32.WaitForSingleObject(h_thread, 10000)
    if result == 0xFFFFFFFF or result == WAIT_TIMEOUT:
        kernel32.CloseHandle(h_thread)
        raise OSError(f"WaitForSingleObject failed/timeout: result={result}")

    exit_code = wintypes.DWORD(0)
    kernel32.GetExitCodeThread(h_thread, ctypes.byref(exit_code))

    kernel32.CloseHandle(h_thread)
    kernel32.VirtualFreeEx(h_process, remote_mem, 0, MEM_RELEASE)

    if exit_code.value == 0:
        raise OSError("LoadLibraryW returned NULL (DLL load failed in target process)")

    logger.debug(f"DLL 注入成功, 模块句柄: 0x{exit_code.value:016X}")
    return True


def launch_with_hook(
        telegram_path: str,
        dll_path: str,
        logger: Logger,
        tdata_name: str | None = None,
        tray_name: str | None = None,
        isolate_appid: bool = False,
        workdir: str | None = None,
        extra_args: str = "",
        no_suspend: bool = False,
) -> int | None:
    """启动 Telegram 并注入 DLL."""
    telegram_path = os.path.abspath(telegram_path)
    if not os.path.isfile(telegram_path):
        logger.error(f"找不到 Telegram: {telegram_path}")
        return None

    dll_path = os.path.abspath(dll_path)
    if not os.path.isfile(dll_path):
        logger.error(f"找不到 DLL: {dll_path}")
        return None

    env = dict(os.environ)
    if tdata_name:
        env["TDATA_NAME"] = tdata_name
    if tray_name:
        env["TRAY_NAME"] = tray_name
    if isolate_appid:
        env["ISOLATE_APPID"] = "1"

    cmd_line = f'"{telegram_path}" -many'
    if workdir:
        workdir_abs = os.path.abspath(workdir)
        cmd_line += f' -workdir "{workdir_abs}"'
    if extra_args:
        if extra_args.startswith("tg://") or extra_args.startswith("http"):
            cmd_line += f' "{extra_args}"'
        else:
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

    logger.debug(f"启动命令行: {cmd_line} (挂起={'否' if no_suspend else '是'})")

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

    _assign_to_job(pi.hProcess, logger)

    if not no_suspend:
        try:
            inject_dll(pi.hProcess, dll_path, logger)
            logger.info("hook 注入成功")
        except Exception as e:
            logger.error(f"注入失败: {e}")
            logger.debug("终止挂起的进程...")
            kernel32.TerminateProcess(pi.hProcess, 1)
            kernel32.CloseHandle(pi.hThread)
            kernel32.CloseHandle(pi.hProcess)
            return None

        prev = kernel32.ResumeThread(pi.hThread)
        logger.debug(f"主线程已恢复 (prev suspend count={prev})")
    else:
        logger.debug("非挂起模式，等待进程初始化后注入...")
        time.sleep(0.3)
        try:
            inject_dll(pi.hProcess, dll_path, logger)
            logger.info("hook 注入成功")
        except Exception as e:
            logger.error(f"注入失败: {e}")
            kernel32.CloseHandle(pi.hThread)
            kernel32.CloseHandle(pi.hProcess)
            return None

    kernel32.CloseHandle(pi.hThread)
    kernel32.CloseHandle(pi.hProcess)
    return pi.dwProcessId


def main() -> int:
    """CLI 注入器入口."""
    parser = argparse.ArgumentParser(
        description="hook DLL 注入器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("telegram", help="Telegram.exe 路径")
    parser.add_argument("--dll", default=None, help="hook.dll 路径")
    parser.add_argument("--tdata", default=None, help="自定义 tdata 目录名")
    parser.add_argument("--workdir", default=None, help="工作目录")
    parser.add_argument("--args", default="", help="额外命令行参数")
    parser.add_argument("--no-suspend", action="store_true", help="不挂起直接注入")
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
