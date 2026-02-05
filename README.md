# Telegram 账户切换器 (TAS)

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![Version](https://img.shields.io/badge/Latest-v1.3.0-brightgreen)
![License](https://img.shields.io/github/license/Zropk66/Telegram-Account-Switcher)

一个用于在 Windows 上快速切换和管理多个 Telegram 账户的工具。

## 功能特性

- **多账户切换**：快速在不同 Telegram 账户之间切换
- **加密支持**：使用 AES-256 加密保护账户数据
- **进程监控**：实时监控 Telegram 进程状态
- **自动恢复**：异常中断后自动恢复账户状态

## 环境要求

- Python 3.12
- Windows 10/11

## 快速开始

```bash
# 克隆项目
git clone https://github.com/Zropk66/Telegram-Account-Switcher.git
cd Telegram-Account-Switcher

# 安装依赖
uv sync

# 打包程序
nuitka --mingw64 --standalone --onefile --windows-console-mode=disable --plugin-enable=pyside6 --output-filename=TAS --output-dir=output --remove-output --lto=yes .\launcher.py

# 运行程序
python TAS.exe
```

打包完成后，可执行文件位于 `output/TAS.exe`。

## 命令行参数

| 参数               | 短参数      | 说明       | 示例                               |
|------------------|----------|----------|----------------------------------|
| --version        | -v       | 查看版本     | `TAS.exe -v`                     |
| --settings       | -c       | 打开设置窗口   | `TAS.exe -c`                     |
| --switch [TAG]   | -s [TAG] | 切换到指定账户  | `TAS.exe -s tag1`                |
| --tag [TAG]      | -t [TAG] | 指定要操作的标签 | `TAS.exe -e -t tag1 -p password` |
| --encrypt        | -e       | 加密所有账户数据 | `TAS.exe -e -p password`         |
| --decrypt        | -d       | 解密所有账户数据 | `TAS.exe -d -p password`         |
| --password [PWD] | -p [PWD] | 指定加密密码   | `TAS.exe -s tag1 -p password`    |

## 使用说明

### 目录结构

```
Telegram/
├── tdata/              # 当前使用的账户
│   └── main/           # 默认账户文件夹
├── tag1/               # 标签账户1
│   └── key_datas       # 加密的账户数据
├── tag2/               # 标签账户2
│   └── key_datas
└── order_files         # 账户配置文件
```

### 基本操作

```bash
# 启动程序
python TAS.exe

# 切换到指定账户
python TAS.exe -s tag1

# 打开设置窗口
python TAS.exe --settings

# 查看版本
python TAS.exe -v
```

### 加密操作

```bash
# 加密所有账户
TAS.exe -e -p [密码]

# 解密所有账户
TAS.exe -d -p [密码]
```

### 切换账户

1. 运行 `TAS.exe -s [标签名] -p [密码]`
2. 程序会自动关闭当前 Telegram 实例
3. 切换并启动目标账户

## 配置文件

首次运行会自动创建 `configs.json` 配置文件：

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

## 注意事项

- **首次运行**：首次运行会提示配置 Telegram 客户端路径
- **账户数据**：加密后的账户数据存储在 `key_datas` 文件
- **日志文件**：运行日志保存在 `TAS.log`
- **权限要求**：如遇权限问题，请尝试以管理员身份运行

## 系统资源

- **内存占用**：运行时空闲约 40MB，账户切换时约 70MB
- **磁盘空间**：单个账户数据约 1-2MB

## 故障排除

1. **无法找到客户端**：检查 `configs.json` 中的路径是否正确
2. **切换失败**：确保 Telegram 已完全关闭后再尝试切换
3. **加密失败**：确认密码正确且账户数据未损坏

## 常见问题

**Q: 切换账户需要多长时间？**
A: 通常 3-5 秒完成账户数据复制和进程启动。

**Q: 如何添加新账户？**
A: 在设置窗口中添加新标签，或手动编辑 `configs.json` 的 `tags` 列表。

**Q: 加密安全吗？**
A: 使用 AES-256 加密，建议设置强密码。

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 `git checkout -b feature/your-feature`
3. 提交更改 `git commit -m "feat: 添加新功能"`
4. 推送分支 `git push origin feature/your-feature`
5. 创建 Pull Request

## 更新日志

查看 [Changelog](Changelog) 了解详细更新内容。

## 许可证

本项目基于 MIT 许可证开源。
