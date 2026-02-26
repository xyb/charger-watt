# charger-watt

[English](README.md) | [中文](README.zh-CN.md)

macOS charger wattage notification — see your charging power the instant you plug in.

![macOS](https://img.shields.io/badge/macOS-only-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-green)
![License](https://img.shields.io/badge/license-MIT-brightgreen)

![screenshot](screenshot.png)

USB-C chargers negotiate power delivery silently — you never know whether your Mac is actually charging at full speed, trickling in at 5 W from a weak adapter, or not charging at all. charger-watt gives you instant feedback: a notification banner pops up the moment you plug in, showing the negotiated wattage, voltage and current. No need to dig through System Information or `ioreg` output.

When you connect a charger, a system notification banner appears showing:

- **Wattage** (e.g. 67W)
- **Negotiated voltage / current** (e.g. 20V / 3.35A)

Event-driven via IOKit — **zero polling**, zero CPU when idle.

## How It Works

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

1. A `CFRunLoop` listens for `IOPSNotificationCreateRunLoopSource` events (kernel-level, no polling).
2. On charger connect, `ioreg` reads adapter wattage, voltage, and current.
3. A macOS Shortcut named **Charger Watt** displays the info as a notification banner.

## Requirements

- macOS 12+ (Monterey or later)
- Python 3.9+ (no third-party packages needed — stdlib only)
- macOS Shortcuts app (pre-installed)

## Installation

### One-liner (copy & paste)

```bash
mkdir -p ~/.local/bin && curl -fsSL -o ~/.local/bin/charger-watt https://raw.githubusercontent.com/xyb/charger-watt/main/charger_watt.py && python3 ~/.local/bin/charger-watt --install
```

### Or clone and install

```bash
git clone https://github.com/xyb/charger-watt.git
cd charger-watt
python3 charger_watt.py --install
```

On first run, `--install` will automatically create the "Charger Watt" shortcut and open the Shortcuts app for you to accept the import. After accepting, run the install command again to complete the setup.

That's it — the monitor starts immediately and auto-starts on every login.

> **Why a Shortcut?** `osascript display notification` and `terminal-notifier` don't work reliably from LaunchAgent background processes due to macOS session/permission restrictions. The Shortcuts app has system-level notification access.

### Quick test (optional)

```bash
python3 charger_watt.py --once
```

If a charger is connected, you'll see something like `67W — 20V / 3.35A`.

## Usage

```
charger-watt [option]

Options:
    (none)          Start the event monitor (foreground)
    --once          Print current charger info and exit
    --install       Install as a LaunchAgent (auto-start on login)
    --uninstall     Remove the LaunchAgent
    --help, -h      Show this help message
```

## Uninstall

```bash
python3 charger_watt.py --uninstall
```

Optionally delete the "Charger Watt" shortcut from the Shortcuts app.

## Logs

```bash
tail -f /tmp/charger-watt.log    # stdout
tail -f /tmp/charger-watt.err    # stderr
```

## License

[MIT](LICENSE)
