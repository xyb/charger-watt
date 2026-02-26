# charger-watt

[English](README.md) | [中文](README.zh-CN.md)

macOS 充电器功率通知 — 插上充电器的瞬间，看到充电功率。

![macOS](https://img.shields.io/badge/macOS-only-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-green)
![License](https://img.shields.io/badge/license-MIT-brightgreen)

![screenshot](screenshot.png)

USB-C 充电器的功率协商是静默完成的 — 你无法直观地知道 Mac 是否在以全速充电、是接了个弱充电器只有 5W 在慢充、还是根本没在充电。charger-watt 让你在插上充电器的瞬间就看到协商的功率、电压和电流，不用再去翻系统信息或敲 `ioreg` 命令。

连接充电器时，系统通知栏会显示：

- **功率**（如 67W）
- **协商的电压 / 电流**（如 20V / 3.35A）

基于 IOKit 事件驱动 — **零轮询**，空闲时零 CPU 占用。

## 工作原理

```
 IOKit power-source event
        │
        ▼
  Python ctypes callback
        │
        ▼
  ioreg AppleSmartBattery ──▶ parse W / V / A
        │
        ▼
  shortcuts run "Charger Watt" ──▶ macOS notification banner
```

1. `CFRunLoop` 监听 `IOPSNotificationCreateRunLoopSource` 事件（内核级，无轮询）。
2. 充电器接入时，通过 `ioreg` 读取适配器的功率、电压和电流。
3. macOS 快捷指令 **Charger Watt** 将信息显示为系统通知横幅。

## 系统要求

- macOS 12+（Monterey 或更高版本）
- Python 3.9+（无第三方依赖，仅使用标准库）
- macOS 快捷指令 app（系统自带）

## 安装

### 一键安装（复制粘贴即可）

```bash
mkdir -p ~/.local/bin && curl -fsSL -o ~/.local/bin/charger-watt https://raw.githubusercontent.com/xyb/charger-watt/main/charger_watt.py && python3 ~/.local/bin/charger-watt --install
```

### 或克隆后安装

```bash
git clone https://github.com/xyb/charger-watt.git
cd charger-watt
python3 charger_watt.py --install
```

首次运行时，`--install` 会自动创建 "Charger Watt" 快捷指令并打开快捷指令 app 让你确认导入。导入后再次运行安装命令即可完成安装。

安装完成后，监控立即生效，每次登录自动启动。

> **为什么用快捷指令？** `osascript display notification` 和 `terminal-notifier` 在 LaunchAgent 后台进程中无法可靠显示通知，这是 macOS 会话/权限限制所致。快捷指令 app 拥有系统级通知权限。

### 快速测试（可选）

```bash
python3 charger_watt.py --once
```

如果已连接充电器，会显示类似 `67W — 20V / 3.35A` 的信息。

## 用法

```
charger-watt [选项]

选项:
    (无参数)        启动事件监控（前台运行）
    --once          查看当前充电信息后退出
    --install       安装为 LaunchAgent（开机自启）
    --uninstall     卸载 LaunchAgent
    --help, -h      显示帮助信息
```

## 卸载

```bash
python3 charger_watt.py --uninstall
```

如不再需要，可在快捷指令 app 中手动删除 "Charger Watt"。

## 日志

```bash
tail -f /tmp/charger-watt.log    # stdout
tail -f /tmp/charger-watt.err    # stderr
```

## 许可证

[MIT](LICENSE)
