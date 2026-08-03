# 端口占用一键清理工具（GUI 版）

一个 Windows 下用图形界面查询并清理端口占用的小工具。封装 `netstat` / `findstr` / `tasklist` / `taskkill`，不再需要每次手动敲命令。

## 功能特性

- **一键查询**：输入端口号，列出该端口所有占用记录（协议、本地地址、外部地址、状态、PID、进程名）。
- **结束进程**：选中记录后一键结束对应 PID，支持「连同子进程一起结束（/T）」。
- **常用端口收藏**：把常用端口（如 8080、3306）存入 `ports.json`，重启后保留。
- **命令日志**：界面底部实时回显实际执行的 `netstat` / `findstr` / `taskkill` 命令与输出，方便排查。
- **安全确认**：结束进程前弹确认框，避免误杀；系统进程结束失败会提示用管理员身份运行。

## 环境要求

- Windows 10 / 11
- Python 3.10+（仅开发 / 打包时需要）

## 开发模式运行

```bash
# 1. 创建并激活虚拟环境
python -m venv env
env\Scripts\activate        # cmd 用 env\Scripts\activate.bat；PowerShell 用 env\Scripts\Activate.ps1

# 2. 安装依赖
pip install PySide6

# 3. 启动 GUI
python port_manager.py
# 也可以直接双击 start.bat
```

## 打包成 exe

双击 `build.bat` 即可自动完成「激活环境 → 安装依赖 → PyInstaller 打包」，产物为 `dist\PortManager.exe`（单文件、无控制台黑框）。

等效的手动命令：

```bash
pyinstaller --onefile --windowed --collect-all PySide6 --name PortManager port_manager.py
```

> 打包后的 exe 体积较大（约 200MB+），这是 PySide6 单文件打包的正常现象。

## 使用说明

1. 在「端口号」输入框填入端口（如 `8080`），点击「查询占用」。
2. 结果表格列出该端口的占用进程；选中某一行，按需勾选「连同子进程一起结束」，点击「结束选中进程」。
3. 「常用端口收藏」区可收藏当前端口、从下拉框加载收藏、删除选中收藏。
4. 若结束系统级进程时提示「拒绝访问」，请右键 `PortManager.exe` 选择「以管理员身份运行」。

## 文件结构

```
portManager/
├── port_core.py      # 核心逻辑：netstat/tasklist/taskkill 封装 + 收藏持久化
├── port_manager.py   # PySide6 主界面
├── requirements.txt  # 依赖声明
├── start.bat         # 开发时一键启动 GUI
├── build.bat         # 打包脚本（纯 ASCII，避免 GBK 控制台中文乱码）
├── PortManager.spec  # PyInstaller 打包配置
├── .gitignore        # 忽略虚拟环境 / 缓存 / 构建产物 / WorkBuddy 数据
└── README.md         # 本文档
```

## 说明

- `ports.json`（收藏数据）在开发时位于脚本目录，打包后位于 `exe` 同目录，保证收藏重启不丢。
- 本工具仅调用 Windows 原生命令查询与结束进程，不修改系统任何配置。
- 查询与结束依赖 `netstat` / `tasklist` / `taskkill`，仅限 Windows 平台。
