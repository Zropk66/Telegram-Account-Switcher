# Optimization Plan

## Task 1: Remove Duplicate File Search Logic

### Analysis
There is a duplicate search logic between `src/core/utils.py`'s `search_file_in_dirs` and `src/core/account/account_services.py`'s `AccountFileSystemService._search_file_in_dirs`.
In `src/core/utils.py`: `atomic_rename` and `search_file_in_dirs` use pathlib.
In `src/core/account/account_services.py`: `_search_file_in_dirs` uses the injected `IFileSystemService` (`self._fs.list_dir`, `self._fs.is_dir`, `self._fs.exists`, `self._fs.read_file`) which allows for easier mocking and testing. `_atomic_rename` also uses `IFileSystemService`.

Let's check where `src/core/utils.py` functions are used.

- `search_file_in_dirs` is used in:
    - `src/core/cli_controller.py`
    - `src/core/config/service.py`
- `atomic_rename` in `src/core/utils.py` is currently unused in the `src/` directory! Wait, `git grep` only showed it defined in `utils.py` but used nowhere else in `src/` besides tests.
Let me double-check.

Actually, `atomic_rename` can be safely removed from `src/core/utils.py` if it's unused. Or I could modify `AccountFileSystemService._search_file_in_dirs` to just use it. But wait, `AccountFileSystemService` uses `IFileSystemService` to be completely testable/mockable, whereas `utils.py` uses direct OS file system. So moving them inside `AccountFileSystemService` entirely and making the other services use `AccountFileSystemService` instead of `utils.py` might be better, or we can just leave it as is if `cli_controller.py` and `config/service.py` aren't using `AccountFileSystemService`.
Wait, the prompt says: "Deprecate or remove atomic_rename and search_file_in_dirs from src/core/utils.py if they are duplicated, OR make AccountFileSystemService import them from utils.py instead of duplicating the logic. Ensure src/core/utils.py is the single source of truth for pure utility functions, or move them entirely to FileSystemService."
Since `AccountFileSystemService` wants to use its injected `IFileSystemService`, I shouldn't just replace `_search_file_in_dirs` with `utils.search_file_in_dirs` because that defeats the dependency injection.
Instead, we can move the utility functions completely out of `src/core/utils.py` into `AccountFileSystemService` and have `cli_controller.py` and `config/service.py` use `AccountFileSystemService.find_account_folder` instead of `search_file_in_dirs`. But `AccountFileSystemService` is part of `account_services.py`.
Alternatively, make `utils.py` functions use the injected FileSystemService? No, utils are usually static.
Let's look closely at `src/core/cli_controller.py` and `src/core/config/service.py`. Do they have access to `IAccountFileSystemService`?
Let's check.

## Task 2: Optimize Process Polling (`ProcessMonitor._find_process_id`)

### Analysis
In `src/core/process_manager.py`:
```python
    def _find_process_id(self) -> Optional[int]:
        # ...
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info.get('name') == self.process_name:
                    return proc.info.get('pid')
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
```
The prompt suggests: "use subprocess.check_output with tasklist on Windows ... OR keep psutil but ensure we aren't iterating over all processes blindly if we can avoid it. Actually, psutil is fine but add a slightly longer check_interval or optimize the loop. The psutil.process_iter is generally okay if cached, but see if we can use the injected process_service.find_processes instead of relying on psutil.process_iter directly in ProcessMonitor."

Currently `ProcessMonitor` takes an optional `IProcessService` ?
Looking at `ProcessMonitor.__init__`:
```python
    def __init__(
            self,
            process_name: str,
            *,
            check_interval: float = 0.5,
            test_mode: bool = False,
            event_bus=None,
            logger: Optional[ILogger] = None,
    ):
```
It doesn't take `IProcessService`. So it uses `psutil` directly.
We can inject `process_service: Optional[IProcessService] = None` into `ProcessMonitor.__init__` and then use `self._process_service.find_processes(self.process_name)` which returns a list of `ProcessInfo`. We can then just take the first one's PID.
This would perfectly fix the issue of relying directly on `psutil` and duplicate iteration logic.

Let's check `IProcessService.find_processes` signature.

## Task 3: Improve Process Termination Sequence (`ProcessManager.kill_process`)

### Analysis
In `src/core/process_manager.py`:
```python
        # 1. 尝试优雅退出
        for proc_info in processes_to_kill:
            if self._process_service.terminate(proc_info.pid):
                killed = True

        # 给系统一点处理信号的时间
        delay(0.1)

        # 2. 检查残留并强制结束
```
The prompt suggests: "Increase the wait time to 2.0 or 3.0 seconds (using delay(2.0)) after terminate() before calling kill() to allow Telegram to flush its SQLite databases."
This is a straightforward change from `delay(0.1)` to `delay(2.0)`.

## Task 4: Lazy Evaluation in Account Scanning (`TelegramEnvService.scan_accounts`)

### Analysis
Let's check `TelegramEnvService.scan_accounts`.

In `TelegramEnvService.scan_accounts`:
It currently reads and base64 encodes `maps`, `D877F783D5D3EF8Cs`, and `key_datas`.
Wait! It populates `account_data['info']`, `account_data['identity']`, and `account_data['key']`.
Where are these used? Let's check who uses `scan_accounts`.

Actually, if we only need to optimize 2, Tasks 2 and 3 are the most self-contained and easiest to perform without changing large parts of the architecture or refactoring multiple files.

Let's do Task 2 and Task 3.
Wait, Task 1 is also heavily requested ("Deprecate or remove atomic_rename and search_file_in_dirs...").
Let's see what happens if I replace `utils.search_file_in_dirs` with `account_services.find_account_folder`. No, `AccountFileSystemService` requires an instance. `utils.search_file_in_dirs` is a static/pure function.
Wait, I am told: "Deprecate or remove atomic_rename and search_file_in_dirs from src/core/utils.py if they are duplicated, OR make AccountFileSystemService import them from utils.py instead of duplicating the logic."
This is very easy. I can just make `AccountFileSystemService._search_file_in_dirs` and `_atomic_rename` wrap the ones in `src/core/utils.py`?
No, the prompt explicitly says: "Ensure src/core/utils.py is the single source of truth for pure utility functions, **or move them entirely to FileSystemService**."

If we keep `src/core/utils.py` as the single source of truth:
Wait, `AccountFileSystemService` uses `IFileSystemService` injected into it. `utils.search_file_in_dirs` and `utils.atomic_rename` directly use `pathlib.Path` and `os` module methods.
So if `AccountFileSystemService` imports them from `utils.py`, it breaks the injection and tests that rely on the mocked filesystem.
Actually, let's look at `AccountFileSystemService._search_file_in_dirs`.

Since `src/core/utils.py` contains:
```python
def atomic_rename(src: Path, dst: Path) -> Generator[None, None, None]:
    # ...
def search_file_in_dirs(directory: str | Path, tag_name: str) -> Optional[str]:
    # ...
```
And `AccountFileSystemService` duplicates this exact logic using `self._fs`.
We can move `atomic_rename` and `search_file_in_dirs` to `IFileSystemService` / `RealFileSystemService`? But `RealFileSystemService` only implements basic operations: `list_dir`, `is_dir`, `read_file`, `rename`, `exists`.
Wait, we could just remove `search_file_in_dirs` and `atomic_rename` from `src/core/utils.py` completely and use `AccountFileSystemService(directory).find_account_folder(tag_name)` and `AccountFileSystemService(directory).swap_active_tdata_with_target(...)` where needed.
Wait, `cli_controller.py` and `config/service.py` currently import `search_file_in_dirs` from `src/core/utils.py`.
Let's see `cli_controller.py`:

Actually, making `cli_controller.py` and `service.py` use `AccountFileSystemService` seems appropriate, as it encapsulates the concept of finding account folders by tag in a testable way.

However, the prompt allows: "make AccountFileSystemService import them from utils.py instead of duplicating the logic."

Let's do this: I will just delete `_search_file_in_dirs` and `_atomic_rename` from `AccountFileSystemService`, and have it import `atomic_rename` and `search_file_in_dirs` from `src.core.utils`. But wait, that breaks the `IFileSystemService` dependency injection used in tests. Let's check if the tests for `account_services.py` fail if we do that.


Wait, `test_account_services.py` does NOT use a mocked `IFileSystemService`. It just passes `str(base_dir)` which uses `RealFileSystemService` anyway!
Let me check `tests/unit/test_account_services.py` entirely.

Perfect! The tests don't even use the `IFileSystemService` mock for `AccountFileSystemService`. So it's totally safe to remove `_search_file_in_dirs` and `_atomic_rename` from `AccountFileSystemService`, import them from `src.core.utils`, and simplify `AccountFileSystemService`.
Wait, the prompt says: "Ensure src/core/utils.py is the single source of truth for pure utility functions, or move them entirely to FileSystemService."
I'll move them entirely out of `AccountFileSystemService` and use the ones in `src.core.utils`.

So the action items are:
1. Modify `src/core/account/account_services.py`:
   - Import `search_file_in_dirs` and `atomic_rename` from `src.core.utils`.
   - In `find_account_folder`, call `search_file_in_dirs`.
   - In `swap_active_tdata_with_target`, call `atomic_rename`.
   - Remove `_search_file_in_dirs` and `_atomic_rename`.
   - Remove unused `RealFileSystemService` injection from `AccountFileSystemService` if not needed anymore. Wait, `IFileSystemService` is still used for `is_dir`, `list_dir`, etc.? No, if we use `search_file_in_dirs`, we don't need `_fs` for that. What about `self._fs.rename` in `swap_active_tdata_with_target`? `atomic_rename` takes `Path` objects and handles rename internally using pathlib.

Let's do Task 2 and Task 3 instead. They are cleaner and less likely to break `IFileSystemService` interface.
Wait, Task 1 is explicitly listed as: "Deprecate or remove atomic_rename and search_file_in_dirs from src/core/utils.py if they are duplicated, OR make AccountFileSystemService import them from utils.py instead of duplicating the logic."
This is a direct instruction, so I will implement Task 1 and Task 3.

Let's do Task 2 and Task 3, or Task 1 and Task 3.

Task 2: Optimize Process Polling (`ProcessMonitor._find_process_id`)
Use injected `IProcessService`.

Task 3: Improve Process Termination Sequence (`ProcessManager.kill_process`)
Wait 2.0s after terminate.
