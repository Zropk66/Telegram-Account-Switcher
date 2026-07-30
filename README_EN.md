# Telegram Account Switcher (TAS)

English | [简体中文](README.md)

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![Version](https://img.shields.io/badge/Latest-v2.0.0-brightgreen)
![License](https://img.shields.io/github/license/Zropk66/Telegram-Account-Switcher)

A tool for quickly switching and managing multiple Telegram accounts on Windows with high performance. Supports both Symlink and DLL Hook launch modes for flexibility and security.

## Features

- **Dual Launch Mode Support**:
  - **Symlink Mode**: Zero-copy account switching by redirecting the `tdata` symbolic link.
  - **Hook Mode (DLL Injection)**: Directly passes data directories to Telegram via DLL injection.
- **Fallback Protection (Hook Fallback)**: Automatically falls back to Symlink mode if Hook injection fails.
- **Data Encryption**: Encrypts sensitive Telegram `key_datas` files using AES-256-GCM.
- **Credential Backup & Key Login**: Extracts and backs up credentials (`key`/`identity`/`info`) for passwordless login recovery.
- **Process & Event Monitoring**: Monitors Telegram process lifecycles and `user_data/configs` login status in real-time.

## Requirements

- Python 3.12+ (managed with `uv`)
- Windows 10/11 (64-bit)

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Zropk66/Telegram-Account-Switcher.git
cd Telegram-Account-Switcher

# Install dependencies
uv sync

# (Optional) Recompile hook.dll: Run inside "x64 Native Tools Command Prompt for VS":
# cd src/hook && compile.bat

# Build executable (output to output/TAS.exe)
python build.py

# Run launcher
python launcher.py
```

After building, the executable will be located at `output/TAS.exe`.

## Command Line Arguments

| Argument         | Short    | Description                         | Example                           |
|------------------|----------|-------------------------------------|-----------------------------------|
| --version        | -v       | Show version                        | `TAS.exe -v`                      |
| --settings       | -c       | Open GUI settings window            | `TAS.exe -c`                      |
| --switch [TAG]   | -s [TAG] | Switch to specified account         | `TAS.exe -s tag1`                 |
| --tag [TAG]      | -t [TAG] | Specify tag for operation           | `TAS.exe -e -t tag1 -p password`  |
| --key-login      | -k       | Force login using backed-up keys    | `TAS.exe -s tag1 -k`              |
| --debug          |          | Enable DEBUG log output             | `TAS.exe --debug`                 |
| --encrypt        | -e       | Encrypt account data                | `TAS.exe -e -p password`          |
| --decrypt        | -d       | Decrypt account data                | `TAS.exe -d -p password`          |
| --password [PWD] | -p [PWD] | Specify encryption/decryption pwd   | `TAS.exe -s tag1 -p password`     |
| --help           | -h       | Show help                           | `TAS.exe -h`                      |

## Directory Structure & Tag Identification

```
Telegram/
├── Telegram.exe            # Telegram executable
├── tdata/                  # Active account symbolic link
├── tdata-account1/         # Account 1 folder
│   ├── tas_tag             # Tag identifier file (contains tag name)
│   ├── key_datas/          # Account key data (supports AES-256)
│   └── ...
├── tdata-account2/         # Account 2 folder
└── ...
```

> Each account directory contains a `tas_tag` file. TAS identifies account tags by reading `tas_tag` contents rather than relying on folder names.

### Account Directory Setup Guide

1. **Automatic Scanning (Recommended)**:
   - Place existing Telegram account folders (such as `tdata` or copied account directories) inside the Telegram installation root directory.
   - Open the TAS Settings window and click **"Auto Scan/Search"**. TAS will discover all accounts and automatically create the required `tas_tag` identifier files.

2. **Manual Setup**:
   - Create a new folder inside your Telegram root directory (e.g., `tdata-work`).
   - Copy account data (`key_datas`, `D877F783D5D3EF8C`, etc.) into `tdata-work`.
   - Create a text file named `tas_tag` inside `tdata-work` and write the tag name (e.g., `work`) into it.

## Configuration File

Running the app automatically creates `config.json`:

```json
{
    "client": "Telegram.exe",
    "path": "D:/Program Files/Telegram",
    "default": "main_account",
    "tags": {
        "tag1": {
            "id": "1001",
            "folder": "tdata-tag1",
            "info": "...",
            "identity": "...",
            "key": "..."
        }
    },
    "log_output": true,
    "launch_mode": "symlink",
    "hook_fallback": true
}
```

* `launch_mode`: Launch mode, options are `symlink` or `hook`.
* `hook_fallback`: Whether to automatically fall back to `symlink` mode when `hook` mode launch fails (default `true`).

## Troubleshooting & Notes

1. **Debug Logging**: Logs default to `INFO` level. Pass `--debug` to inspect detailed execution traces or check `TAS.log`.
2. **Symlink Permissions**: Creating symbolic links in Windows requires developer mode or administrator permissions.
3. **Hook Fallback**: If DLL injection is blocked by anti-virus software, enable `hook_fallback` for automatic fallback.

## License

This project is licensed under the MIT License.
