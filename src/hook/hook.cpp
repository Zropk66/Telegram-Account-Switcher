#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <propsys.h>
#include <propkey.h>
#include <string>
#include <mutex>
#include <atomic>
#include <memory>
#include <stdio.h>
#include <stdarg.h>
#include <share.h>

#include "minhook/MinHook.h"

namespace {

std::wstring g_target = L"tdata";
std::wstring g_trayName = L"";
bool g_enabled = false;
bool g_isolateAppId = false;

// TAS IPC communication
static HANDLE g_ipc_pipe = INVALID_HANDLE_VALUE;
static std::mutex g_ipcMutex;
static std::atomic<bool> g_is_listener{false};
static std::atomic<bool> g_has_failed_pipe{false};
static std::atomic<bool> g_trying_original{false};
static std::wstring g_failed_pipe_name;
static DWORD g_failed_pipe_b = 0, g_failed_pipe_c = 0, g_failed_pipe_d = 0;
static DWORD g_failed_pipe_e = 0, g_failed_pipe_f = 0, g_failed_pipe_g = 0;

static HANDLE g_listener_mutex = NULL;
static const wchar_t* kListenerMutexName = L"Global\\TAS_HOOK_LISTENER_MUTEX";

// =====================================================================
// Diagnostic logging
// =====================================================================

std::mutex g_logMutex;
FILE* g_logFile = nullptr;

void DebugLog(const char* fmt, ...) {
	char timebuf[32];
	SYSTEMTIME st;
	GetLocalTime(&st);
	snprintf(timebuf, sizeof(timebuf), "[%02d:%02d:%02d.%03d] ",
		st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);

	std::lock_guard<std::mutex> lock(g_logMutex);
	if (!g_logFile) {
		g_logFile = _fsopen("hook.log", "a", _SH_DENYNO);
		if (!g_logFile) return;
	}
	fputs(timebuf, g_logFile);
	va_list ap;
	va_start(ap, fmt);
	vfprintf(g_logFile, fmt, ap);
	va_end(ap);
	fputc('\n', g_logFile);
	fflush(g_logFile);
}

std::wstring GetTagSuffix() {
	return !g_trayName.empty() ? g_trayName : g_target;
}

// =====================================================================
// Path rewriting
// =====================================================================

constexpr const wchar_t* kFrom = L"tdata";
constexpr size_t kFromLen = 5;

bool IsSeparator(wchar_t c) {
	return c == L'\\' || c == L'/';
}

bool RewritePath(LPCWSTR path, std::wstring &out) {
	if (!path || !*path) return false;
	if (!g_enabled) return false;

	if (wcsncmp(path, L"\\\\.\\pipe\\", 9) == 0) {
		out.assign(path);
		out.append(L"_");
		out.append(g_target);
		return true;
	}

	const wchar_t* logPos = wcsstr(path, L"log.txt");
	if (logPos != nullptr) {
		const bool leftOk = (logPos == path) || IsSeparator(logPos[-1]);
		if (leftOk) {
			size_t prefixLen = logPos - path;
			std::wstring prefix(path, prefixLen);
			bool alreadyHasTarget = false;
			if (prefix.size() >= g_target.size() + 1) {
				wchar_t lastChar = prefix.back();
				if (IsSeparator(lastChar)) {
					std::wstring sub = prefix.substr(prefix.size() - 1 - g_target.size(), g_target.size());
					if (sub == g_target) {
						alreadyHasTarget = true;
					}
				}
			}
			if (!alreadyHasTarget) {
				out = prefix + g_target + L"\\" + L"log.txt";
				return true;
			}
		}
	}

	const auto &to = g_target;

	const wchar_t *scan = path;
	bool needRedirect = false;
	while ((scan = wcsstr(scan, kFrom)) != nullptr) {
		const bool leftOk = (scan == path) || IsSeparator(scan[-1]);
		const bool rightOk = (scan[kFromLen] == L'\0') || IsSeparator(scan[kFromLen]);
		if (leftOk && rightOk) {
			needRedirect = true;
			break;
		}
		scan += kFromLen;
	}
	if (!needRedirect) return false;

	out.assign(path);
	if (to.size() > kFromLen) {
		out.reserve(out.size() + (to.size() - kFromLen));
	}
	size_t pos = 0;
	while ((pos = out.find(kFrom, pos)) != std::wstring::npos) {
		const size_t end = pos + kFromLen;
		const bool leftOk = (pos == 0) || IsSeparator(out[pos - 1]);
		const bool rightOk = (end >= out.size()) || IsSeparator(out[end]);
		if (leftOk && rightOk) {
			out.replace(pos, kFromLen, to);
			pos += to.size();
		} else {
			pos = end;
		}
	}
	return true;
}

struct PathBuf {
	std::wstring buf;
	LPCWSTR ptr;
	PathBuf(LPCWSTR p) : ptr(p) {
		if (g_enabled && p) {
			if (RewritePath(p, buf)) {
				ptr = buf.c_str();
			}
		}
	}
};

// =====================================================================
// Original function pointers
// =====================================================================

using pfnCreateFileW = HANDLE(WINAPI*)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
using pfnCreateDirectoryW = BOOL(WINAPI*)(LPCWSTR, LPSECURITY_ATTRIBUTES);
using pfnCreateDirectoryExW = BOOL(WINAPI*)(LPCWSTR, LPCWSTR, LPSECURITY_ATTRIBUTES);
using pfnRemoveDirectoryW = BOOL(WINAPI*)(LPCWSTR);
using pfnDeleteFileW = BOOL(WINAPI*)(LPCWSTR);
using pfnMoveFileExW = BOOL(WINAPI*)(LPCWSTR, LPCWSTR, DWORD);
using pfnCopyFileW = BOOL(WINAPI*)(LPCWSTR, LPCWSTR, BOOL);
using pfnCopyFileExW = BOOL(WINAPI*)(LPCWSTR, LPCWSTR, LPPROGRESS_ROUTINE, LPVOID, LPBOOL, DWORD);
using pfnGetFileAttributesW = DWORD(WINAPI*)(LPCWSTR);
using pfnGetFileAttributesExW = BOOL(WINAPI*)(LPCWSTR, GET_FILEEX_INFO_LEVELS, LPVOID);
using pfnSetFileAttributesW = BOOL(WINAPI*)(LPCWSTR, DWORD);
using pfnFindFirstFileW = HANDLE(WINAPI*)(LPCWSTR, LPWIN32_FIND_DATAW);
using pfnFindFirstFileExW = HANDLE(WINAPI*)(LPCWSTR, FINDEX_INFO_LEVELS, LPVOID, FINDEX_SEARCH_OPS, LPVOID, DWORD);
using pfnCreateFile2 = HRESULT(WINAPI*)(LPCWSTR, DWORD, DWORD, DWORD, LPCREATEFILE2_EXTENDED_PARAMETERS);
using pfnCreateNamedPipeW = HANDLE(WINAPI*)(LPCWSTR, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, LPSECURITY_ATTRIBUTES);
using pfnShell_NotifyIconW = BOOL(WINAPI*)(DWORD dwMessage, PNOTIFYICONDATAW lpData);
using pfnShell_NotifyIconA = BOOL(WINAPI*)(DWORD dwMessage, PNOTIFYICONDATAA lpData);
using pfnSetWindowTextW = BOOL(WINAPI*)(HWND hWnd, LPCWSTR lpString);
using pfnSetCurrentProcessExplicitAppUserModelID = HRESULT(WINAPI*)(PCWSTR AppID);
using pfnSHGetPropertyStoreForWindow = HRESULT(WINAPI*)(HWND hwnd, REFIID riid, void** ppv);

pfnCreateFileW          o_CreateFileW = nullptr;
pfnCreateDirectoryW      o_CreateDirectoryW = nullptr;
pfnCreateDirectoryExW    o_CreateDirectoryExW = nullptr;
pfnRemoveDirectoryW      o_RemoveDirectoryW = nullptr;
pfnDeleteFileW           o_DeleteFileW = nullptr;
pfnMoveFileExW          o_MoveFileExW = nullptr;
pfnCopyFileW             o_CopyFileW = nullptr;
pfnCopyFileExW           o_CopyFileExW = nullptr;
pfnGetFileAttributesW    o_GetFileAttributesW = nullptr;
pfnGetFileAttributesExW  o_GetFileAttributesExW = nullptr;
pfnSetFileAttributesW    o_SetFileAttributesW = nullptr;
pfnFindFirstFileW        o_FindFirstFileW = nullptr;
pfnFindFirstFileExW      o_FindFirstFileExW = nullptr;
pfnCreateFile2           o_CreateFile2 = nullptr;
pfnCreateNamedPipeW      o_CreateNamedPipeW = nullptr;
pfnShell_NotifyIconW     o_Shell_NotifyIconW = nullptr;
pfnShell_NotifyIconA     o_Shell_NotifyIconA = nullptr;
pfnSetWindowTextW        o_SetWindowTextW = nullptr;
pfnSetCurrentProcessExplicitAppUserModelID o_SetCurrentProcessExplicitAppUserModelID = nullptr;
pfnSHGetPropertyStoreForWindow o_SHGetPropertyStoreForWindow = nullptr;

// =====================================================================
// raw callers
// =====================================================================

static HANDLE RawCreateNamedPipeW(pfnCreateNamedPipeW fn, LPCWSTR a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g, LPSECURITY_ATTRIBUTES h) {
	__try {
		return fn(a, b, c, d, e, f, g, h);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return INVALID_HANDLE_VALUE;
	}
}

static HANDLE SafeCreateFileW(pfnCreateFileW fn, LPCWSTR a, DWORD b, DWORD c,
		LPSECURITY_ATTRIBUTES d, DWORD e, DWORD f, HANDLE g) {
	__try {
		return fn(a, b, c, d, e, f, g);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return INVALID_HANDLE_VALUE;
	}
}

static BOOL SafeCreateDirectoryW(pfnCreateDirectoryW fn, LPCWSTR a, LPSECURITY_ATTRIBUTES b) {
	__try {
		return fn(a, b);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return FALSE;
	}
}

static BOOL SafeCreateDirectoryExW(pfnCreateDirectoryExW fn, LPCWSTR a, LPCWSTR b, LPSECURITY_ATTRIBUTES c) {
	__try {
		return fn(a, b, c);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return FALSE;
	}
}

static BOOL SafeRemoveDirectoryW(pfnRemoveDirectoryW fn, LPCWSTR a) {
	__try {
		return fn(a);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return FALSE;
	}
}

static BOOL SafeDeleteFileW(pfnDeleteFileW fn, LPCWSTR a) {
	__try {
		return fn(a);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return FALSE;
	}
}

static BOOL SafeMoveFileExW(pfnMoveFileExW fn, LPCWSTR a, LPCWSTR b, DWORD c) {
	__try {
		return fn(a, b, c);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return FALSE;
	}
}

static BOOL SafeCopyFileW(pfnCopyFileW fn, LPCWSTR a, LPCWSTR b, BOOL c) {
	__try {
		return fn(a, b, c);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return FALSE;
	}
}

static BOOL SafeCopyFileExW(pfnCopyFileExW fn, LPCWSTR a, LPCWSTR b,
		LPPROGRESS_ROUTINE c, LPVOID d, LPBOOL e, DWORD f) {
	__try {
		return fn(a, b, c, d, e, f);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return FALSE;
	}
}

static DWORD SafeGetFileAttributesW(pfnGetFileAttributesW fn, LPCWSTR a) {
	__try {
		return fn(a);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return INVALID_FILE_ATTRIBUTES;
	}
}

static BOOL SafeGetFileAttributesExW(pfnGetFileAttributesExW fn, LPCWSTR a,
		GET_FILEEX_INFO_LEVELS b, LPVOID c) {
	__try {
		return fn(a, b, c);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return FALSE;
	}
}

static BOOL SafeSetFileAttributesW(pfnSetFileAttributesW fn, LPCWSTR a, DWORD b) {
	__try {
		return fn(a, b);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return FALSE;
	}
}

static HANDLE SafeFindFirstFileW(pfnFindFirstFileW fn, LPCWSTR a, LPWIN32_FIND_DATAW b) {
	__try {
		return fn(a, b);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return INVALID_HANDLE_VALUE;
	}
}

static HANDLE SafeFindFirstFileExW(pfnFindFirstFileExW fn, LPCWSTR a,
		FINDEX_INFO_LEVELS b, LPVOID c, FINDEX_SEARCH_OPS d, LPVOID e, DWORD f) {
	__try {
		return fn(a, b, c, d, e, f);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return INVALID_HANDLE_VALUE;
	}
}

static HRESULT SafeCreateFile2(pfnCreateFile2 fn, LPCWSTR a, DWORD b, DWORD c,
		DWORD d, LPCREATEFILE2_EXTENDED_PARAMETERS e) {
	__try {
		return fn(a, b, c, d, e);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		SetLastError(ERROR_ACCESS_DENIED);
		return HRESULT_FROM_WIN32(ERROR_ACCESS_DENIED);
	}
}

// =====================================================================
// TAS IPC communication
// =====================================================================
static bool AcquireListenerMutex(DWORD timeout = 0) {
    if (g_listener_mutex == NULL) {
        g_listener_mutex = CreateMutexW(NULL, FALSE, kListenerMutexName);
    }
    if (g_listener_mutex == NULL) {
        DebugLog("AcquireListenerMutex: CreateMutex failed, err=%d", GetLastError());
        return false;
    }
    DWORD result = WaitForSingleObject(g_listener_mutex, timeout);
    if (result == WAIT_OBJECT_0 || result == WAIT_ABANDONED) {
        DebugLog("AcquireListenerMutex: acquired (result=%d, timeout=%d)", result, timeout);
        return true;
    }
    DebugLog("AcquireListenerMutex: not acquired (result=%d, timeout=%d)", result, timeout);
    return false;
}

static void ReleaseListenerMutex() {
    if (g_listener_mutex) {
        ReleaseMutex(g_listener_mutex);
    }
}

void SendIPC(const wchar_t* fmt, ...) {
    wchar_t buf[1024];
    va_list ap;
    va_start(ap, fmt);
    vswprintf(buf, 1024, fmt, ap);
    va_end(ap);

    std::lock_guard<std::mutex> lock(g_ipcMutex);
    if (g_ipc_pipe == INVALID_HANDLE_VALUE) return;

    DWORD written;
    DWORD len = (DWORD)(wcslen(buf) + 1) * sizeof(wchar_t);
    BOOL ok = WriteFile(g_ipc_pipe, buf, len, &written, NULL);
    if (!ok) {
        DebugLog("SendIPC: WriteFile failed, err=%d, msg='%ws'", GetLastError(), buf);
    }
}

DWORD WINAPI PipeListenerThread(LPVOID param) {
    HANDLE pipe = (HANDLE)param;
    DebugLog("PipeListener: started, pipe=%p", pipe);

    while (g_ipc_pipe != INVALID_HANDLE_VALUE) {
        BOOL connected = ConnectNamedPipe(pipe, NULL)
            ? TRUE : (GetLastError() == ERROR_PIPE_CONNECTED);

        if (!connected) {
            DebugLog("PipeListener: ConnectNamedPipe failed, err=%d", GetLastError());
            break;
        }

        DebugLog("PipeListener: client connected");

        BYTE buf[8192];
        DWORD bytesRead = 0;
        if (ReadFile(pipe, buf, sizeof(buf) - 1, &bytesRead, NULL) && bytesRead > 0) {
            buf[bytesRead] = 0;

            const char* data = (const char*)buf;
            const char* tg = nullptr;

            for (DWORD i = 0; i + 5 <= bytesRead; i++) {
                if (memcmp(data + i, "tg://", 5) == 0) {
                    tg = data + i;
                    break;
                }
            }

            if (!tg) {
                for (DWORD i = 0; i + 10 <= bytesRead; i += 2) {
                    if (memcmp(data + i, "t\0g\0:\0/\0/\0", 10) == 0) {
                        char url[1024] = {0};
                        int j = 0;
                        for (DWORD k = i; k + 1 < bytesRead && j < 1023; k += 2) {
                            char c = data[k];
                            if (c == 0) break;
                            url[j++] = c;
                        }
                        SendIPC(L"URL_FOUND:%hs", url);
                        DebugLog("PipeListener: found URL (UTF16): %hs", url);
                        tg = nullptr;
                        break;
                    }
                }
            }

            if (tg) {
                char url[1024] = {0};
                int j = 0;
                for (DWORD k = (DWORD)(tg - data); k < bytesRead && j < 1023; k++) {
                    char c = data[k];
                    if (c == ' ' || c == '"' || c == '\0' || c == '\r' || c == '\n') break;
                    url[j++] = c;
                }
                SendIPC(L"URL_FOUND:%hs", url);
                DebugLog("PipeListener: found URL (ASCII): %hs", url);
            }
        }

        FlushFileBuffers(pipe);
        DisconnectNamedPipe(pipe);
        DebugLog("PipeListener: client disconnected");
    }

    CloseHandle(pipe);
    DebugLog("PipeListener: exited");
    return 0;
}

struct OriginalPipeParams {
    std::wstring pipeName;
    DWORD b, c, d, e, f, g_time;
};

DWORD WINAPI TryCreateOriginalPipeThread(LPVOID param) {
    std::unique_ptr<OriginalPipeParams> p((OriginalPipeParams*)param);
    LPCWSTR pipeName = p->pipeName.c_str();

    DebugLog("TryCreateOriginalPipe: attempting original pipe: %ls (nMaxInstances forced to 1, orig=%d)", pipeName, p->d);

    if (!AcquireListenerMutex()) {
        g_failed_pipe_name = p->pipeName;
        g_failed_pipe_b = p->b; g_failed_pipe_c = p->c; g_failed_pipe_d = p->d;
        g_failed_pipe_e = p->e; g_failed_pipe_f = p->f; g_failed_pipe_g = p->g_time;
        g_has_failed_pipe.store(true);
        g_trying_original.store(false);
        SendIPC(L"NOT_LISTENING");
        DebugLog("TryCreateOriginalPipe: not listener (mutex held by another instance)");
        return 0;
    }

    HANDLE rawPipe = RawCreateNamedPipeW(o_CreateNamedPipeW, pipeName, p->b, p->c, 1, p->e, p->f, p->g_time, NULL);

    DWORD createErr = rawPipe == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    DebugLog("TryCreateOriginalPipe: result=%p, err=%d", rawPipe, createErr);

    if (rawPipe != INVALID_HANDLE_VALUE) {
        if (g_is_listener.load()) {
            CloseHandle(rawPipe);
            ReleaseListenerMutex();
            g_trying_original.store(false);
            DebugLog("TryCreateOriginalPipe: already listener, closing duplicate");
            return 0;
        }
        g_is_listener.store(true);
        g_trying_original.store(false);
        LPCWSTR shortName = pipeName + 9;
        DebugLog("TryCreateOriginalPipe: about to send LISTENING");
        SendIPC(L"LISTENING:%ls", shortName);
        DebugLog("TryCreateOriginalPipe: became listener, pipe=%ls", shortName);
        CreateThread(NULL, 0, PipeListenerThread, rawPipe, 0, NULL);
    } else {
        ReleaseListenerMutex();
        g_failed_pipe_name = p->pipeName;
        g_failed_pipe_b = p->b; g_failed_pipe_c = p->c; g_failed_pipe_d = p->d;
        g_failed_pipe_e = p->e; g_failed_pipe_f = p->f; g_failed_pipe_g = p->g_time;
        g_has_failed_pipe.store(true);
        g_trying_original.store(false);
        SendIPC(L"NOT_LISTENING");
        DebugLog("TryCreateOriginalPipe: not listener (pipe creation failed)");
    }
    return 0;
}

void TryCreateOriginalPipe(LPCWSTR pipeName, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g_time, LPSECURITY_ATTRIBUTES h) {
    if (g_ipc_pipe == INVALID_HANDLE_VALUE) {
        DebugLog("TryCreateOriginalPipe: skip (no IPC pipe)");
        return;
    }
    if (g_is_listener.load()) return;
    if (g_has_failed_pipe.load()) return;
    if (g_trying_original.exchange(true)) return;
    if (wcsncmp(pipeName, L"\\\\.\\pipe\\Global\\", 16) != 0) {
        g_trying_original.store(false);
        DebugLog("TryCreateOriginalPipe: skip (not Global pipe): %ls", pipeName);
        return;
    }

    auto* params = new OriginalPipeParams{
        std::wstring(pipeName), b, c, d, e, f, g_time
    };
    CreateThread(NULL, 0, TryCreateOriginalPipeThread, params, 0, NULL);
}

DWORD WINAPI IPCRecvThread(LPVOID) {
    wchar_t buf[512];
    DWORD bytesRead;

    DebugLog("IPCRecv: thread started, pipe=%p", g_ipc_pipe);

    while (g_ipc_pipe != INVALID_HANDLE_VALUE) {
        DWORD bytesAvail = 0;
        if (!PeekNamedPipe(g_ipc_pipe, NULL, 0, NULL, &bytesAvail, NULL)) {
            DWORD err = GetLastError();
            DebugLog("IPCRecv: PeekNamedPipe failed, err=%d", err);
            break;
        }

        if (bytesAvail == 0) {
            Sleep(50);
            continue;
        }

        BOOL ok = ReadFile(g_ipc_pipe, buf, sizeof(buf) - 2, &bytesRead, NULL);
        DWORD err = ok ? 0 : GetLastError();
        DebugLog("IPCRecv: ReadFile ok=%d, bytesRead=%d, err=%d", ok, bytesRead, err);

        if (!ok || bytesRead == 0) break;

        buf[bytesRead / sizeof(wchar_t)] = 0;
        DebugLog("IPCRecv: received '%ws'", buf);

        if (wcscmp(buf, L"RETRY_LISTEN") == 0 && g_has_failed_pipe.load() && !g_is_listener.load()) {
            if (!AcquireListenerMutex(3000)) {
                DebugLog("RETRY_LISTEN: mutex still held by another instance");
                SendIPC(L"NOT_LISTENING");
            } else {
                HANDLE rawPipe = o_CreateNamedPipeW(
                    g_failed_pipe_name.c_str(),
                    g_failed_pipe_b, g_failed_pipe_c, 1,
                    g_failed_pipe_e, g_failed_pipe_f, g_failed_pipe_g,
                    NULL
                );

                if (rawPipe != INVALID_HANDLE_VALUE) {
                    g_is_listener.store(true);
                    g_has_failed_pipe.store(false);
                    LPCWSTR shortName = g_failed_pipe_name.c_str() + 9;
                    SendIPC(L"LISTENING:%ls", shortName);
                    DebugLog("RETRY_LISTEN: became listener, pipe=%ls", shortName);
                    CreateThread(NULL, 0, PipeListenerThread, rawPipe, 0, NULL);
                } else {
                    ReleaseListenerMutex();
                    DebugLog("RETRY_LISTEN: still failed, err=%d", GetLastError());
                }
            }
        }
    }

    DebugLog("IPCRecv: TAS disconnected");
    std::lock_guard<std::mutex> lock(g_ipcMutex);
    g_ipc_pipe = INVALID_HANDLE_VALUE;
    return 0;
}

DWORD WINAPI ConnectToTASThread(LPVOID) {
    for (int i = 0; i < 60; i++) {
        g_ipc_pipe = SafeCreateFileW(
            o_CreateFileW,
            L"\\\\.\\pipe\\TAS_HOOK_IPC",
            GENERIC_READ | GENERIC_WRITE,
            0, NULL, OPEN_EXISTING, 0, NULL
        );
        if (g_ipc_pipe != INVALID_HANDLE_VALUE) break;

        DWORD err = GetLastError();
        if (i == 0 || i == 10 || i == 30 || i == 59) {
            DebugLog("ConnectToTAS: retry %d, err=%d", i, err);
        }
        Sleep(200);
    }

    if (g_ipc_pipe == INVALID_HANDLE_VALUE) {
        DebugLog("ConnectToTAS: failed to connect after 60 retries");
        return 1;
    }

    DebugLog("ConnectToTAS: connected, pipe=%p", g_ipc_pipe);

    DWORD mode = PIPE_READMODE_MESSAGE;
    if (SetNamedPipeHandleState(g_ipc_pipe, &mode, NULL, NULL)) {
        DebugLog("ConnectToTAS: set pipe to message mode OK");
    } else {
        DebugLog("ConnectToTAS: SetNamedPipeHandleState failed, err=%d", GetLastError());
    }

    SendIPC(L"REGISTER:%ls:%d", g_target.c_str(), GetCurrentProcessId());
    CreateThread(NULL, 0, IPCRecvThread, NULL, 0, NULL);
    return 0;
}

void ConnectToTAS() {
    CreateThread(NULL, 0, ConnectToTASThread, NULL, 0, NULL);
}

// =====================================================================
// Hook implementations
// =====================================================================

HANDLE WINAPI h_CreateFileW(LPCWSTR a, DWORD b, DWORD c, LPSECURITY_ATTRIBUTES d, DWORD e, DWORD f, HANDLE g) {
	PathBuf p(a);
	return SafeCreateFileW(o_CreateFileW, p.ptr, b, c, d, e, f, g);
}

BOOL WINAPI h_CreateDirectoryW(LPCWSTR a, LPSECURITY_ATTRIBUTES b) {
	PathBuf p(a);
	return SafeCreateDirectoryW(o_CreateDirectoryW, p.ptr, b);
}

BOOL WINAPI h_CreateDirectoryExW(LPCWSTR a, LPCWSTR b, LPSECURITY_ATTRIBUTES c) {
	PathBuf p(a);
	PathBuf q(b);
	return SafeCreateDirectoryExW(o_CreateDirectoryExW, p.ptr, q.ptr, c);
}

BOOL WINAPI h_RemoveDirectoryW(LPCWSTR a) {
	PathBuf p(a);
	return SafeRemoveDirectoryW(o_RemoveDirectoryW, p.ptr);
}

BOOL WINAPI h_DeleteFileW(LPCWSTR a) {
	PathBuf p(a);
	return SafeDeleteFileW(o_DeleteFileW, p.ptr);
}

BOOL WINAPI h_MoveFileExW(LPCWSTR a, LPCWSTR b, DWORD c) {
	PathBuf p(a);
	PathBuf q(b);
	return SafeMoveFileExW(o_MoveFileExW, p.ptr, q.ptr, c);
}

BOOL WINAPI h_CopyFileW(LPCWSTR a, LPCWSTR b, BOOL c) {
	PathBuf p(a);
	PathBuf q(b);
	return SafeCopyFileW(o_CopyFileW, p.ptr, q.ptr, c);
}

BOOL WINAPI h_CopyFileExW(LPCWSTR a, LPCWSTR b, LPPROGRESS_ROUTINE c, LPVOID d, LPBOOL e, DWORD f) {
	PathBuf p(a);
	PathBuf q(b);
	return SafeCopyFileExW(o_CopyFileExW, p.ptr, q.ptr, c, d, e, f);
}

DWORD WINAPI h_GetFileAttributesW(LPCWSTR a) {
	PathBuf p(a);
	return SafeGetFileAttributesW(o_GetFileAttributesW, p.ptr);
}

BOOL WINAPI h_GetFileAttributesExW(LPCWSTR a, GET_FILEEX_INFO_LEVELS b, LPVOID c) {
	PathBuf p(a);
	return SafeGetFileAttributesExW(o_GetFileAttributesExW, p.ptr, b, c);
}

BOOL WINAPI h_SetFileAttributesW(LPCWSTR a, DWORD b) {
	PathBuf p(a);
	return SafeSetFileAttributesW(o_SetFileAttributesW, p.ptr, b);
}

HANDLE WINAPI h_FindFirstFileW(LPCWSTR a, LPWIN32_FIND_DATAW b) {
	PathBuf p(a);
	return SafeFindFirstFileW(o_FindFirstFileW, p.ptr, b);
}

HANDLE WINAPI h_FindFirstFileExW(LPCWSTR a, FINDEX_INFO_LEVELS b, LPVOID c, FINDEX_SEARCH_OPS d, LPVOID e, DWORD f) {
	PathBuf p(a);
	return SafeFindFirstFileExW(o_FindFirstFileExW, p.ptr, b, c, d, e, f);
}

HRESULT WINAPI h_CreateFile2(LPCWSTR a, DWORD b, DWORD c, DWORD d, LPCREATEFILE2_EXTENDED_PARAMETERS e) {
	PathBuf p(a);
	return SafeCreateFile2(o_CreateFile2, p.ptr, b, c, d, e);
}

HANDLE WINAPI h_CreateNamedPipeW(LPCWSTR a, DWORD b, DWORD c, DWORD d, DWORD e, DWORD f, DWORD g, LPSECURITY_ATTRIBUTES h) {
	PathBuf p(a);
	DebugLog("CreateNamedPipeW: %ls -> %ls (enabled=%d)", a, p.ptr, g_enabled ? 1 : 0);
	HANDLE result = RawCreateNamedPipeW(o_CreateNamedPipeW, p.ptr, b, c, d, e, f, g, h);
	DebugLog("CreateNamedPipeW: result=%p, err=%d", result, result == INVALID_HANDLE_VALUE ? GetLastError() : 0);

	if (g_enabled && result != INVALID_HANDLE_VALUE) {
		TryCreateOriginalPipe(a, b, c, d, e, f, g, h);
	}

	return result;
}

BOOL WINAPI h_Shell_NotifyIconW(DWORD dwMessage, PNOTIFYICONDATAW lpData) {
	if (g_enabled && lpData && (dwMessage == NIM_ADD || dwMessage == NIM_MODIFY)) {
		if (lpData->uFlags & NIF_TIP) {
			std::wstring tag = GetTagSuffix();
			std::wstring origTip = lpData->szTip;

			if (!origTip.empty() && origTip.find(L"- [" + tag + L"]") == std::wstring::npos) {
				std::wstring newTip = origTip + L" - [" + tag + L"]";
				if (newTip.size() < 128) {
					wcscpy_s(lpData->szTip, newTip.c_str());
				}
			} else if (origTip.empty()) {
				std::wstring newTip = L"Telegram - [" + tag + L"]";
				if (newTip.size() < 128) {
					wcscpy_s(lpData->szTip, newTip.c_str());
				}
			}
		}
	}
	return o_Shell_NotifyIconW ? o_Shell_NotifyIconW(dwMessage, lpData) : FALSE;
}

BOOL WINAPI h_Shell_NotifyIconA(DWORD dwMessage, PNOTIFYICONDATAA lpData) {
	if (g_enabled && lpData && (dwMessage == NIM_ADD || dwMessage == NIM_MODIFY)) {
		if (lpData->uFlags & NIF_TIP) {
			std::wstring tagW = GetTagSuffix();
			std::string origTip = lpData->szTip;

			char tagA[128] = { 0 };
			WideCharToMultiByte(CP_ACP, 0, tagW.c_str(), -1, tagA, sizeof(tagA), NULL, NULL);
			std::string tagStr(tagA);

			if (!origTip.empty() && origTip.find("- [" + tagStr + "]") == std::string::npos) {
				std::string newTip = origTip + " - [" + tagStr + "]";
				if (newTip.size() < 128) {
					strcpy_s(lpData->szTip, newTip.c_str());
				}
			}
		}
	}
	return o_Shell_NotifyIconA ? o_Shell_NotifyIconA(dwMessage, lpData) : FALSE;
}

BOOL WINAPI h_SetWindowTextW(HWND hWnd, LPCWSTR lpString) {
	if (g_enabled && lpString) {
		std::wstring tag = GetTagSuffix();
		std::wstring origText = lpString;
		if (!origText.empty() && origText.find(L"- [" + tag + L"]") == std::wstring::npos) {
			std::wstring newText = origText + L" - [" + tag + L"]";
			return o_SetWindowTextW(hWnd, newText.c_str());
		}
	}
	return o_SetWindowTextW(hWnd, lpString);
}

HRESULT WINAPI h_SetCurrentProcessExplicitAppUserModelID(PCWSTR AppID) {
	if (g_enabled && g_isolateAppId && AppID) {
		std::wstring tag = GetTagSuffix();
		std::wstring newAppID = AppID;
		newAppID += L"." + tag;
		DebugLog("SetCurrentProcessExplicitAppUserModelID Hook: orig='%ws', new='%ws'", AppID, newAppID.c_str());
		return o_SetCurrentProcessExplicitAppUserModelID ? o_SetCurrentProcessExplicitAppUserModelID(newAppID.c_str()) : S_OK;
	}
	return o_SetCurrentProcessExplicitAppUserModelID ? o_SetCurrentProcessExplicitAppUserModelID(AppID) : S_OK;
}

class ProxyPropertyStore : public IPropertyStore {
private:
	IPropertyStore* m_realStore;
	LONG m_refCount;
public:
	ProxyPropertyStore(IPropertyStore* store) : m_realStore(store), m_refCount(1) {}
	virtual ~ProxyPropertyStore() { if (m_realStore) m_realStore->Release(); }

	HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppvObject) override {
		if (riid == IID_IUnknown || riid == IID_IPropertyStore) {
			*ppvObject = static_cast<IPropertyStore*>(this);
			AddRef();
			return S_OK;
		}
		return m_realStore->QueryInterface(riid, ppvObject);
	}
	ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&m_refCount); }
	ULONG STDMETHODCALLTYPE Release() override {
		ULONG count = InterlockedDecrement(&m_refCount);
		if (count == 0) { delete this; return 0; }
		return count;
	}
	HRESULT STDMETHODCALLTYPE GetCount(DWORD* cProps) override { return m_realStore->GetCount(cProps); }
	HRESULT STDMETHODCALLTYPE GetAt(DWORD iProp, PROPERTYKEY* pkey) override { return m_realStore->GetAt(iProp, pkey); }
	HRESULT STDMETHODCALLTYPE GetValue(REFPROPERTYKEY key, PROPVARIANT* pv) override { return m_realStore->GetValue(key, pv); }
	HRESULT STDMETHODCALLTYPE SetValue(REFPROPERTYKEY key, REFPROPVARIANT propvar) override {
		if (g_enabled && g_isolateAppId && IsEqualPropertyKey(key, PKEY_AppUserModel_ID)) {
			if (propvar.vt == VT_LPWSTR && propvar.pwszVal) {
				std::wstring tag = GetTagSuffix();
				std::wstring newAppID = propvar.pwszVal;
				newAppID += L"." + tag;
				PROPVARIANT newPropvar;
				PropVariantInit(&newPropvar);
				newPropvar.vt = VT_LPWSTR;
				newPropvar.pwszVal = const_cast<wchar_t*>(newAppID.c_str());
				DebugLog("SHGetPropertyStoreForWindow SetValue PKEY_AppUserModel_ID Hook: orig='%ws', new='%ws'", propvar.pwszVal, newAppID.c_str());
				HRESULT hr = m_realStore->SetValue(key, newPropvar);
				return hr;
			}
		}
		return m_realStore->SetValue(key, propvar);
	}
	HRESULT STDMETHODCALLTYPE Commit() override { return m_realStore->Commit(); }
};

HRESULT WINAPI h_SHGetPropertyStoreForWindow(HWND hwnd, REFIID riid, void** ppv) {
	HRESULT hr = o_SHGetPropertyStoreForWindow ? o_SHGetPropertyStoreForWindow(hwnd, riid, ppv) : E_FAIL;
	if (SUCCEEDED(hr) && ppv && *ppv && g_enabled && g_isolateAppId) {
		if (riid == IID_IPropertyStore) {
			IPropertyStore* realStore = static_cast<IPropertyStore*>(*ppv);
			*ppv = new ProxyPropertyStore(realStore);
		}
	}
	return hr;
}

// =====================================================================
// Hook installation via MinHook
// =====================================================================

struct HookDef {
	const wchar_t* dll;
	const char* func;
	void* hookFn;
	void** origPtr;
};

void InstallAllHooks() {
	DebugLog("InstallAllHooks start (MinHook)");

	LoadLibraryW(L"shell32.dll");
	LoadLibraryW(L"user32.dll");

	MH_STATUS mi = MH_Initialize();
	if (mi != MH_OK) {
		DebugLog("MH_Initialize failed: %s", MH_StatusToString(mi));
		return;
	}
	DebugLog("MH_Initialize OK");

	HookDef defs[] = {
		{ L"kernelbase.dll", "CreateFileW",           (void*)h_CreateFileW,           (void**)&o_CreateFileW },
		{ L"kernelbase.dll", "CreateDirectoryW",     (void*)h_CreateDirectoryW,      (void**)&o_CreateDirectoryW },
		{ L"kernelbase.dll", "CreateDirectoryExW",    (void*)h_CreateDirectoryExW,    (void**)&o_CreateDirectoryExW },
		{ L"kernelbase.dll", "RemoveDirectoryW",     (void*)h_RemoveDirectoryW,      (void**)&o_RemoveDirectoryW },
		{ L"kernelbase.dll", "DeleteFileW",          (void*)h_DeleteFileW,           (void**)&o_DeleteFileW },
		{ L"kernelbase.dll", "MoveFileExW",          (void*)h_MoveFileExW,           (void**)&o_MoveFileExW },
		{ L"kernelbase.dll", "CopyFileW",            (void*)h_CopyFileW,             (void**)&o_CopyFileW },
		{ L"kernelbase.dll", "CopyFileExW",          (void*)h_CopyFileExW,           (void**)&o_CopyFileExW },
		{ L"kernelbase.dll", "GetFileAttributesW",   (void*)h_GetFileAttributesW,    (void**)&o_GetFileAttributesW },
		{ L"kernelbase.dll", "GetFileAttributesExW", (void*)h_GetFileAttributesExW,  (void**)&o_GetFileAttributesExW },
		{ L"kernelbase.dll", "SetFileAttributesW",   (void*)h_SetFileAttributesW,    (void**)&o_SetFileAttributesW },
		{ L"kernelbase.dll", "FindFirstFileW",       (void*)h_FindFirstFileW,        (void**)&o_FindFirstFileW },
		{ L"kernelbase.dll", "FindFirstFileExW",     (void*)h_FindFirstFileExW,      (void**)&o_FindFirstFileExW },
		{ L"kernelbase.dll", "CreateFile2",          (void*)h_CreateFile2,           (void**)&o_CreateFile2 },
		{ L"kernelbase.dll", "CreateNamedPipeW",     (void*)h_CreateNamedPipeW,      (void**)&o_CreateNamedPipeW },
		{ L"shell32.dll",    "Shell_NotifyIconW",    (void*)h_Shell_NotifyIconW,     (void**)&o_Shell_NotifyIconW },
		{ L"shell32.dll",    "Shell_NotifyIconA",    (void*)h_Shell_NotifyIconA,     (void**)&o_Shell_NotifyIconA },
		{ L"shell32.dll",    "SetCurrentProcessExplicitAppUserModelID", (void*)h_SetCurrentProcessExplicitAppUserModelID, (void**)&o_SetCurrentProcessExplicitAppUserModelID },
		{ L"shell32.dll",    "SHGetPropertyStoreForWindow", (void*)h_SHGetPropertyStoreForWindow, (void**)&o_SHGetPropertyStoreForWindow },
		{ L"user32.dll",     "SetWindowTextW",       (void*)h_SetWindowTextW,        (void**)&o_SetWindowTextW },
	};

	const int count = sizeof(defs) / sizeof(defs[0]);

	for (int i = 0; i < count; i++) {
		const auto& d = defs[i];

		HMODULE hMod = GetModuleHandleW(d.dll);
		if (!hMod) {
			hMod = GetModuleHandleW(L"kernel32.dll");
		}
		void* target = hMod ? (void*)GetProcAddress(hMod, d.func) : nullptr;
		if (!target) {
			DebugLog("  [%d] %s: target NOT FOUND", i, d.func);
			continue;
		}

		MH_STATUS ms = MH_CreateHook(target, d.hookFn, d.origPtr);
		if (ms != MH_OK) {
			DebugLog("  [%d] %s: MH_CreateHook failed: %s", i, d.func, MH_StatusToString(ms));
			continue;
		}

		DebugLog("  [%d] %s @ %p: created OK", i, d.func, target);

		ms = MH_QueueEnableHook(target);
		if (ms != MH_OK) {
			DebugLog("  [%d] %s: MH_QueueEnableHook failed: %s", i, d.func, MH_StatusToString(ms));
		}
	}

	MH_STATUS ma = MH_ApplyQueued();
	if (ma == MH_OK) {
		DebugLog("All hooks activated atomically (thread-safe)");
	} else {
		DebugLog("MH_ApplyQueued failed: %s", MH_StatusToString(ma));
	}

	DebugLog("InstallAllHooks done");
}

// =====================================================================
// Config loading
// =====================================================================

std::wstring Trim(std::wstring s) {
	const wchar_t* ws = L" \t\r\n";
	size_t a = s.find_first_not_of(ws);
	if (a == std::wstring::npos) return L"";
	size_t b = s.find_last_not_of(ws);
	return s.substr(a, b - a + 1);
}

bool ParseNamedArg(const wchar_t* cmdLine, const wchar_t* key, std::wstring& outVal) {
	if (!cmdLine || !*cmdLine) return false;

	const size_t keyLen = wcslen(key);
	const wchar_t* pos = wcsstr(cmdLine, key);
	while (pos != nullptr) {
		bool leftOk = (pos == cmdLine) || (pos[-1] == L' ' || pos[-1] == L'\t');
		bool rightOk = (pos[keyLen] == L'\0') || (pos[keyLen] == L' ' || pos[keyLen] == L'\t' || pos[keyLen] == L'=');

		if (leftOk && rightOk) {
			const wchar_t* p = pos + keyLen;
			while (*p == L' ' || *p == L'\t' || *p == L'=') p++;
			if (*p == L'\0') break;

			std::wstring val;
			if (*p == L'"') {
				p++;
				while (*p != L'\0' && *p != L'"') {
					val.push_back(*p++);
				}
			} else {
				while (*p != L'\0' && *p != L' ' && *p != L'\t') {
					val.push_back(*p++);
				}
			}
			val = Trim(val);
			if (!val.empty()) {
				outVal = val;
				return true;
			}
		}
		pos = wcsstr(pos + keyLen, key);
	}
	return false;
}

void LoadConfig() {
	wchar_t val[256] = { 0 };
	DWORD n = GetEnvironmentVariableW(L"TDATA_NAME", val, 256);
	if (n > 0 && n < 256) {
		g_target = Trim(val);
		if (!g_target.empty()) g_enabled = true;
	} else {
		LPCWSTR cmdLine = GetCommandLineW();
		std::wstring cmdTarget;
		if (ParseNamedArg(cmdLine, L"-tdata_name", cmdTarget)) {
			g_target = cmdTarget;
			g_enabled = true;
		}
	}

	wchar_t trayVal[256] = { 0 };
	DWORD nTray = GetEnvironmentVariableW(L"TRAY_NAME", trayVal, 256);
	if (nTray > 0 && nTray < 256) {
		g_trayName = Trim(trayVal);
	} else {
		LPCWSTR cmdLine = GetCommandLineW();
		std::wstring cmdTray;
		if (ParseNamedArg(cmdLine, L"-tray_name", cmdTray)) {
			g_trayName = cmdTray;
		}
	}

	wchar_t isolateVal[256] = { 0 };
	DWORD nIsolate = GetEnvironmentVariableW(L"ISOLATE_APPID", isolateVal, 256);
	if (nIsolate > 0 && nIsolate < 256) {
		std::wstring valStr = Trim(isolateVal);
		g_isolateAppId = (valStr == L"1" || valStr == L"true" || valStr == L"TRUE");
	} else {
		LPCWSTR cmdLine = GetCommandLineW();
		std::wstring cmdIsolate;
		if (ParseNamedArg(cmdLine, L"-isolate_appid", cmdIsolate)) {
			g_isolateAppId = (cmdIsolate == L"1" || cmdIsolate == L"true" || cmdIsolate == L"TRUE");
		} else if (wcsstr(cmdLine, L"-isolate_appid") != nullptr) {
			g_isolateAppId = true;
		}
	}

	DebugLog("LoadConfig: TDATA_NAME='%ws' TRAY_NAME='%ws' isolate_appid=%d enabled=%d", g_target.c_str(), g_trayName.c_str(), g_isolateAppId, g_enabled);
}

} // namespace

// =====================================================================
// DllMain
// =====================================================================

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID) {
	if (reason == DLL_PROCESS_ATTACH) {
		DisableThreadLibraryCalls(hModule);
		DebugLog("DllMain: DLL_PROCESS_ATTACH");
		LoadConfig();
		InstallAllHooks();
		if (g_enabled) {
			ConnectToTAS();
		}
		DebugLog("DllMain: initialization complete");
	} else if (reason == DLL_PROCESS_DETACH) {
		DebugLog("DllMain: DLL_PROCESS_DETACH");
		if (g_is_listener.load()) {
			ReleaseListenerMutex();
			g_is_listener.store(false);
			DebugLog("DllMain: listener mutex released");
		}
		if (g_ipc_pipe != INVALID_HANDLE_VALUE) {
			SendIPC(L"BYE:%d", GetCurrentProcessId());
			std::lock_guard<std::mutex> lock(g_ipcMutex);
			CloseHandle(g_ipc_pipe);
			g_ipc_pipe = INVALID_HANDLE_VALUE;
		}
		MH_Uninitialize();
		if (g_logFile) {
			fclose(g_logFile);
			g_logFile = nullptr;
		}
	}
	return TRUE;
}