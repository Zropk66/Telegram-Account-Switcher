#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string>
#include <mutex>
#include <stdio.h>
#include <stdarg.h>

#include "minhook/MinHook.h"

namespace {

std::wstring g_target = L"tdata";
bool g_enabled = false;

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
		fopen_s(&g_logFile, "hook_debug.log", "a");
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

// =====================================================================
// raw callers
// =====================================================================

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

bool ParseTdataNameArg(const wchar_t* cmdLine, std::wstring& outTarget) {
	if (!cmdLine || !*cmdLine) return false;

	const wchar_t* key = L"-tdata_name";
	const size_t keyLen = 11;
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
				outTarget = val;
				return true;
			}
		}
		pos = wcsstr(pos + keyLen, key);
	}
	return false;
}

void LoadConfig() {
	// 优先度 1: 从命令行参数 -tdata_name 获取（权重最高）
	LPCWSTR cmdLine = GetCommandLineW();
	std::wstring cmdTarget;
	if (ParseTdataNameArg(cmdLine, cmdTarget)) {
		g_target = cmdTarget;
		g_enabled = true;
		DebugLog("LoadConfig: from cmdline -tdata_name='%ws' enabled=%d", g_target.c_str(), g_enabled);
		return;
	}

	// 优先度 2: 环境变量 TDATA_NAME（降级回退）
	wchar_t val[256] = { 0 };
	DWORD n = GetEnvironmentVariableW(L"TDATA_NAME", val, 256);
	if (n > 0 && n < 256) {
		g_target = Trim(val);
		if (!g_target.empty()) {
			g_enabled = true;
			DebugLog("LoadConfig: from TDATA_NAME='%ws' enabled=%d", g_target.c_str(), g_enabled);
			return;
		}
	}
	DebugLog("LoadConfig: no valid -tdata_name arg or TDATA_NAME env set, redirect disabled");
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
		DebugLog("DllMain: initialization complete");
	} else if (reason == DLL_PROCESS_DETACH) {
		DebugLog("DllMain: DLL_PROCESS_DETACH");
		MH_Uninitialize();
		if (g_logFile) {
			fclose(g_logFile);
			g_logFile = nullptr;
		}
	}
	return TRUE;
}
