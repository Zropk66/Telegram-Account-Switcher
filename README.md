# Telegram 账户切换器 (TAS)

[English](README_EN.md) | 简体中文

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![Version](https://img.shields.io/badge/Latest-v2.0.0-brightgreen)
![License](https://img.shields.io/github/license/Zropk66/Telegram-Account-Switcher)

一个用于在 Windows 上快速高效切换和管理多个 Telegram 账户的工具。支持符号链接（Symlink）与 Hook 注入两种启动模式，兼具安全性与高效体验。

## 功能特性

- **双启动模式支持**：
  - **符号链接模式（Symlink）**：通过重定向 `tdata` 符号链接完成零拷贝账户切换。
  - **Hook 注入模式（DLL Hook）**：直接注入 Telegram 参数指定数据目录，免去快捷重定向。
- **降级保护机制（Hook Fallback）**：Hook 启动失败时可自动平滑降级为软链接模式启动。
- **加密保护**：基于 AES-256-GCM 算法加密 Telegram 敏感 `key_datas` 数据。
- **登录凭证备份与恢复**：支持凭证（Key/Identity/Info）提取与无密码重新登录重建。
- **精准进程与文件监控**：实时监控 Telegram 进程生命周期与 `user_data/configs` 登录状态，退出自动安全落盘。

## 环境要求

- Python 3.12+ (使用 `uv` 依赖管理)
- Windows 10/11 (64-bit)

## 快速开始

```bash
# 克隆项目
git clone https://github.com/Zropk66/Telegram-Account-Switcher.git
cd Telegram-Account-Switcher

# 安装依赖
uv sync

# (可选) 重新编译 hook.dll：请在 "x64 Native Tools Command Prompt for VS" 终端中运行：
# cd src/hook && compile.bat

# 打包程序 (自动生成到 output/TAS.exe)
python build.py

# 运行程序
python launcher.py
```

打包完成后，可执行文件位于 `output/TAS.exe`。

## 命令行参数

| 参数               | 短参数      | 说明                           | 示例                               |
|------------------|----------|------------------------------|----------------------------------|
| --version        | -v       | 查看版本                         | `TAS.exe -v`                     |
| --settings       | -c       | 打开 GUI 设置窗口                   | `TAS.exe -c`                     |
| --switch [TAG]   | -s [TAG] | 切换并启动指定账户                     | `TAS.exe -s tag1`                |
| --tag [TAG]      | -t [TAG] | 指定要操作的标签                     | `TAS.exe -e -t tag1 -p password` |
| --key-login      | -k       | 强制使用备份 Key 重新登录               | `TAS.exe -s tag1 -k`             |
| --debug          |          | 启用 DEBUG 调试日志输出              | `TAS.exe --debug`                |
| --encrypt        | -e       | 加密账户数据                       | `TAS.exe -e -p password`         |
| --decrypt        | -d       | 解密账户数据                       | `TAS.exe -d -p password`         |
| --password [PWD] | -p [PWD] | 指定加密/解密密码                    | `TAS.exe -s tag1 -p password`    |
| --help           | -h       | 查看帮助信息                       | `TAS.exe -h`                     |

## 目录结构与识别原理

```
Telegram/
├── Telegram.exe            # Telegram 客户端程序
├── tdata/                  # 当前活跃账户软链接（指向目标账户目录）
├── tdata-account1/         # 账户1 目录
│   ├── tas_tag             # 账户标签标识文件（内容为对应 tag 名称）
│   ├── key_datas/          # 账户密钥数据 (支持 AES-256 加密)
│   └── ...
├── tdata-account2/         # 账户2 目录
└── ...
```

> 每个账户目录中都包含一个 `tas_tag` 标识文件。TAS 通过读取 `tas_tag` 的内容识别账户标签，而非依赖物理文件夹名称。

### 账户放置与管理方法

1. **自动扫描放置（推荐）**：
   - 将现有 Telegram 账户文件夹（如 `tdata` 或复制出的其他账户目录）直接放在 Telegram 客户端根目录下。
   - 打开 TAS 客户端进入“设置”窗口，点击 **“自动获取/扫描”** 按钮，TAS 将自动检测所有账户数据并自动补全生成 `tas_tag` 标识文件。

2. **手动放置**：
   - 在 Telegram 程序根目录下新建文件夹（例如 `tdata-work`）。
   - 将目标账户的数据内容（`key_datas` / `D877F783D5D3EF8C` 等）放入该文件夹中。
   - 在该文件夹根目录下创建一个无后缀的文本文件 `tas_tag`，并在文件中写入对应的标签名称（例如 `work`）。

## 配置文件说明

首次运行会在应用根目录自动创建 `config.json` 配置文件：

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

* `launch_mode`: 启动模式，可选 `symlink` (符号链接模式) 或 `hook` (DLL Hook 注入模式)。
* `hook_fallback`: Hook 模式启动失败时，是否允许自动降级为软链接模式启动（默认 `true`）。

## 注意事项与故障排除

1. **调试日志**：默认仅输出 `INFO` 级日志，如遇启动或切换问题，可添加 `--debug` 参数运行查看详细跟踪信息或检查 `TAS.log`。
2. **符号链接权限**：软链接模式创建符链接需要系统权限，建议以管理员身份运行程序或在 Windows 设置中启用“开发者模式”。
3. **Hook 模式**：Hook 模式适用于不想频繁修改 `tdata` 软链接的场景；若 Hook 注入被安全软件拦截，可开启 `hook_fallback` 自动降级。

## 许可证

本项目基于 MIT 许可证开源。
