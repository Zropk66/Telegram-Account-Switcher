# Telegram Account Switcher (TAS)

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![Version](https://img.shields.io/badge/Latest-v1.2.2-brightgreen)
![License](https://img.shields.io/github/license/Zropk66/Telegram-Account-Switcher)

A tool for quickly switching and managing multiple Telegram accounts on Windows.

## Features

- **Multi-account Switching**: Quickly switch between different Telegram accounts
- **Encryption Support**: Protect account data with AES-256 encryption
- **Process Monitoring**: Real-time monitoring of Telegram process status
- **Auto Recovery**: Automatically recover account status after abnormal interruption

## Requirements

- Python 3.12
- Windows 10/11

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Zropk66/Telegram-Account-Switcher.git
cd Telegram-Account-Switcher

# Install dependencies
uv sync

# Build the program
nuitka --mingw64 --standalone --onefile --windows-console-mode=disable --plugin-enable=pyside6 --output-filename=TAS --output-dir=output --remove-output --lto=yes .\launcher.py

# Run the program
python TAS.exe
```

After building, the executable will be located at `output/TAS.exe`.

## Command Line Arguments

| Argument         | Short    | Description                 | Example                       |
|------------------|----------|-----------------------------|-------------------------------|
| --version        | -v       | Show version                | `TAS.exe -v`                  |
| --settings       | -c       | Open settings window        | `TAS.exe -c`                  |
| --switch [TAG]   | -s [TAG] | Switch to specified account | `TAS.exe -s tag1`             |
| --help           | -h       | Show help                   | `TAS.exe -h`                  |
| --encrypt        | -e       | Encrypt all account data    | `TAS.exe -e -p password`      |
| --decrypt        | -d       | Decrypt all account data    | `TAS.exe -d -p password`      |
| --password [PWD] | -p [PWD] | Specify encryption password | `TAS.exe -s tag1 -p password` |

## Usage Guide

### Directory Structure

```
Telegram/
├── tdata/              # Currently used account
│   └── main/           # Default account folder
├── tag1/               # Tagged account 1
│   └── key_datas       # Encrypted account data
├── tag2/               # Tagged account 2
│   └── key_datas
└── order_files         # Account configuration file
```

### Basic Operations

```bash
# Start the program
python TAS.exe

# Switch to specified account
python TAS.exe -s tag1

# Open settings window
python TAS.exe --settings

# Show version
python TAS.exe -v
```

### Encryption Operations

```bash
# Encrypt all accounts
TAS.exe -e -p [password]

# Decrypt all accounts
TAS.exe -d -p [password]
```

### Switching Accounts

1. Run `TAS.exe -s [tag_name] -p [password]`
2. The program will automatically close the current Telegram instance
3. Switch to and start the target account

## Configuration File

The first run will automatically create a `configs.json` configuration file:

```json
{
  "client": "Telegram.exe",
  "path": "C:/Path/To/Telegram",
  "default": "main",
  "tags": [
    "tag1",
    "tag2"
  ],
  "log_output": true
}
```

## Notes

- **First Run**: The first run will prompt you to configure the Telegram client path
- **Account Data**: Encrypted account data is stored in the `key_datas` file
- **Log File**: Runtime logs are saved in `TAS.log`
- **Permissions**: If you encounter permission issues, try running as administrator

## System Resources

- **Memory Usage**: ~40MB idle, ~70MB during account switching
- **Disk Space**: ~1-2MB per account

## Troubleshooting

1. **Unable to find client**: Check if the path in `configs.json` is correct
2. **Switching failed**: Ensure Telegram is completely closed before attempting to switch
3. **Encryption failed**: Confirm the password is correct and account data is not corrupted

## FAQ

**Q: How long does it take to switch accounts?**
A: Usually takes 3-5 seconds to complete account data copying and process startup.

**Q: How to add a new account?**
A: Add a new tag in the settings window, or manually edit the `tags` list in `configs.json`.

**Q: Is encryption secure?**
A: Uses AES-256 encryption, strong passwords are recommended.

## Contributing

Issue reports and Pull Requests are welcome!

1. Fork this repository
2. Create a feature branch `git checkout -b feature/your-feature`
3. Commit your changes `git commit -m "feat: add new feature"`
4. Push to the branch `git push origin feature/your-feature`
5. Create a Pull Request

## Changelog

See [Changelog](CHANGELOG.md) for detailed update information.

## License

This project is licensed under the MIT License.
