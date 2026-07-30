# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

- **Environment Setup**: `uv sync` (requires Python 3.12 and [uv](https://github.com/astral-sh/uv))
- **Run Application**: `python src/main.py` (or `python launcher.py` if present at root)
- **Build/Package**: `nuitka --mingw64 --standalone --onefile --windows-console-mode=disable --plugin-enable=pyside6 --output-filename=TAS --output-dir=output --remove-output --lto=yes .\launcher.py`
- **Tests**: 
    - Run all tests: `pytest`
    - Run a specific test file: `pytest tests/unit/test_config_service.py`
    - Run a specific test case: `pytest tests/unit/test_config_service.py::test_function_name`
- **CLI Mode**: `python launcher.py [args]` (e.g., `-s tag1` to switch, `-c` for settings, `-e -p password` to encrypt)

## Code Architecture

### High-Level Structure
- **Entry Point**: `src/main.py` defines `main()` which is the entry point, coordinating global dependencies and the application lifecycle.
- **Core Logic (`src/core/`)**:
    - **Account Management (`src/core/account/`)**:
        - `account_switcher.py`: Business logic for switching accounts (`AccountSwitcher`).
        - `account_operations.py`: Low-level directory swapping, encryption state checks, and failure fallbacks (`switch_to_tag`, `restore_default`).
        - `account_monitor.py`: Background thread that watches the Telegram process lifecycle.
    - **Configuration (`src/core/config/`)**:
        - Persisted state stored in `config.json` using `ConfigStorage`.
        - `ConfigService` provides typed access.
    - **Process Management**: `process_manager.py` handles tracking, starting, and gracefully killing the `Telegram.exe` client.
    - **Encryption**: `crypto.py` handles AES-256-GCM encryption/decryption of Telegram's internal `key_datas` files.
    - **Telegram Internals (`src/core/telegram_data_decrypter/`)**: Utilities for dissecting and reconstructing Telegram's internal binary data formats, useful for passwordless login injection.
- **UI (`src/ui/`)**:
    - Built with PySide6 (Qt).
    - `settings_ui.py` contains logic for the main settings dialog.
    - `popup.py` handles global alert and confirmation dialogs.
    - `adapters.py` glues the CLI/Core exceptions to Qt message boxes.

### Account Management Pattern
The tool operates by managing directories inside the Telegram folder.
1. The active account is always in the `tdata/` directory.
2. Inactive accounts are stored in subdirectories named after their "tags" (e.g., `tag1/`).
3. Inside each account directory, there's a `tas_tag` file that contains the tag name. The tool identifies accounts by this file, not the folder name.
4. Switching (`AccountSwitcher.process`) involves:
    - Killing existing `Telegram.exe` processes.
    - Moving current `tdata/` content back to its dynamically found tag folder.
    - Moving the target tag folder's content to `tdata/`.
    - Decrypting the target's `key_datas` file (if encrypted).
    - Restarting Telegram.

### Error Handling
- The core throws `TASException` and `TASCipherException` defined in `src/core/exceptions.py`.
- `main.py` uses `sys.excepthook = handle_global_exception` to catch unhandled errors and show a PySide popup before exiting.
- The `AccountSwitcher` uses a context manager (`switching_session`) to ensure that if a switch fails midway, the default account is restored automatically.
