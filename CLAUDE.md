# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

charger-watt is a macOS utility that shows a notification banner with charger wattage, voltage, and current when a MacBook is plugged in. It uses IOKit event notifications (zero polling) and displays notifications via the macOS Shortcuts app.

## Common Commands

```bash
# Run the monitor in foreground (for testing)
python3 charger_watt.py

# Check current charger info once
python3 charger_watt.py --once

# Install as LaunchAgent (auto-start on login)
python3 charger_watt.py --install

# Uninstall LaunchAgent
python3 charger_watt.py --uninstall

# View logs
tail -f /tmp/charger-watt.log
tail -f /tmp/charger-watt.err
```

## Architecture

### Core Components

1. **charger_watt.py** - Main daemon that:
   - Uses `ctypes` to call IOKit/CoreFoundation APIs directly (no external dependencies)
   - Registers for power source change events via `IOPSNotificationCreateRunLoopSource`
   - Parses `ioreg -rn AppleSmartBattery` output to extract adapter details
   - Triggers macOS Shortcuts to display notifications

2. **setup_shortcut.py** - Standalone utility to create and import the "Charger Watt" shortcut

### Notification Mechanism

The app uses macOS Shortcuts for notifications because `osascript display notification` and `terminal-notifier` don't work reliably from LaunchAgent background processes due to macOS session/permission restrictions.

The shortcut (named "Charger Watt"):
- Accepts text input via stdin
- Displays it as a system notification banner
- Created programmatically as a binary plist, signed with `shortcuts sign`, and imported

### Data Flow

```
Charger plug/unplug
        ↓
IOKit power-source event (kernel)
        ↓
Python ctypes callback (_on_power_event)
        ↓
Debounce timer (1.5s to handle event flurries)
        ↓
ioreg AppleSmartBattery → parse Watts/Voltage/Current
        ↓
shortcuts run "Charger Watt" (stdin: "⚡ 67W — 20V / 3.35A")
        ↓
macOS notification banner
```

### LaunchAgent Installation

`--install` creates `~/Library/LaunchAgents/me.xieyanbo.charger-watt.plist` with:
- Runs at login (`RunAtLoad`)
- Restarts if killed (`KeepAlive`)
- Logs to `/tmp/charger-watt.log` and `/tmp/charger-watt.err`
- PATH includes common tool locations (`~/.asdf/shims`, `/opt/homebrew/bin`, etc.)

## Key Implementation Details

- **Event-driven, no polling**: Uses `CFRunLoop` with `IOPSNotificationCreateRunLoopSource`
- **Debounce handling**: 1.5-second debounce on power events to handle flurries during plug/unplug
- **ioreg parsing**: Extracts `Watts`, `AdapterVoltage` (mV), and `Current` (mA) from the `AdapterDetails` dict in ioreg output
- **Python path resolution**: `_resolve_python()` preserves virtualenv paths (no realpath) for LaunchAgent compatibility

## Files

- `charger_watt.py` - Main daemon (400+ lines, self-contained)
- `setup_shortcut.py` - Shortcut creation utility (can be used standalone)
- `screenshot.png` - UI screenshot for README

## Requirements

- macOS 12+ (Monterey or later)
- Python 3.9+ (stdlib only, no third-party packages)
- macOS Shortcuts app (pre-installed)

## No Test Suite

This project has no automated tests. Test manually with `--once` flag or by plugging/unplugging a charger while monitor is running.
