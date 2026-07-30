@echo off
setlocal

where cl >nul 2>&1
if errorlevel 1 (
    echo ERROR: MSVC compiler cl.exe not found.
    echo Please run this script in MSVC Command Prompt or run vcvars64.bat first.
    exit /b 1
)
echo [1/3] Compiling MinHook library ...
cl /nologo /O2 /MT /W3 /utf-8 /c minhook\buffer.c minhook\hook.c minhook\trampoline.c minhook\hde64.c /Fo:minhook\
if errorlevel 1 (
    echo [ERROR] MinHook compilation failed.
    exit /b 1
)
echo [2/3] Compiling hook.cpp ...
cl /nologo /LD /EHa /std:c++17 /O2 /MT /W3 /utf-8 /c hook.cpp
if errorlevel 1 (
    echo [ERROR] hook.cpp compilation failed.
    exit /b 1
)
echo [3/3] Linking ...
link /nologo /DLL /OUT:hook.dll hook.obj minhook\buffer.obj minhook\hook.obj minhook\trampoline.obj minhook\hde64.obj kernel32.lib user32.lib
if errorlevel 1 (
    echo [ERROR] Linking failed.
    exit /b 1
)
echo [OK] hook.dll (MinHook) built successfully.
endlocal
