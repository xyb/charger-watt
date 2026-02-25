#!/usr/bin/env python3
"""macOS charger plug-in wattage notification (event-driven, zero polling).

Uses IOKit IOPSNotificationCreateRunLoopSource for kernel-level
power-source change events via ctypes.  When a charger is connected,
a notification banner appears showing the negotiated wattage, voltage
and current.

Requires macOS and a "Charger Watt" shortcut in the Shortcuts app that
accepts text input and displays it as a notification.  See README for setup.
"""
from __future__ import annotations

import ctypes
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# IOKit / CoreFoundation ctypes
# ---------------------------------------------------------------------------

_iokit = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/IOKit.framework/IOKit"
)
_cf = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
)

_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p)

_iokit.IOPSNotificationCreateRunLoopSource.argtypes = [_CB, ctypes.c_void_p]
_iokit.IOPSNotificationCreateRunLoopSource.restype = ctypes.c_void_p

_cf.CFRunLoopGetCurrent.argtypes = []
_cf.CFRunLoopGetCurrent.restype = ctypes.c_void_p
_cf.CFRunLoopAddSource.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
]
_cf.CFRunLoopRun.argtypes = []
_cf.CFRunLoopRun.restype = None

_kCFRunLoopDefaultMode = ctypes.c_void_p.in_dll(_cf, "kCFRunLoopDefaultMode")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_prev_connected: bool | None = None
_debounce_timer: threading.Timer | None = None
_DEBOUNCE_SEC = 1.5

PLIST_LABEL = "me.xieyanbo.charger-watt"
PLIST_PATH = Path.home() / "Library/LaunchAgents" / f"{PLIST_LABEL}.plist"
SHORTCUT_NAME = "Charger Watt"

# ---------------------------------------------------------------------------
# ioreg helpers
# ---------------------------------------------------------------------------

def _ioreg() -> str:
    r = subprocess.run(
        ["/usr/sbin/ioreg", "-rn", "AppleSmartBattery"],
        capture_output=True, text=True,
    )
    return r.stdout


def _field(info: str, key: str) -> str | None:
    for line in info.splitlines():
        if f'"{key}"' in line and "= " in line:
            return line.split("= ", 1)[1].strip()
    return None


def _adapter_int(info: str, key: str) -> int | None:
    for line in info.splitlines():
        if '"AdapterDetails"' in line:
            m = re.search(rf'"{key}"=(\d+)', line)
            return int(m.group(1)) if m else None
    return None

# ---------------------------------------------------------------------------
# Notification — system banner via Shortcuts
# ---------------------------------------------------------------------------

def _resolve_python() -> str:
    """Return an absolute path to the current Python interpreter.

    Preserves virtualenv paths (no realpath) so the LaunchAgent runs
    in the same environment the user installed from.  Falls back to
    ``which`` when sys.executable is not absolute.
    """
    exe = sys.executable
    if os.path.isabs(exe):
        return exe
    r = subprocess.run(
        ["which", exe], capture_output=True, text=True,
    )
    resolved = r.stdout.strip()
    if r.returncode == 0 and resolved:
        return resolved
    return os.path.abspath(exe)


def _notify(title: str, subtitle: str) -> None:
    msg = f"{title} — {subtitle}" if subtitle else title
    subprocess.run(
        ["shortcuts", "run", SHORTCUT_NAME],
        input=msg, text=True, timeout=10,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _shortcut_exists() -> bool:
    r = subprocess.run(["shortcuts", "list"], capture_output=True, text=True)
    return SHORTCUT_NAME in r.stdout.splitlines()


def _setup_shortcut() -> None:
    """Create, sign and open the Charger Watt shortcut for import."""
    shortcut = {
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 4274264319,
            "WFWorkflowIconGlyphNumber": 59764,
        },
        "WFWorkflowActions": [
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
                "WFWorkflowActionParameters": {
                    "WFNotificationActionBody": "",
                    "WFNotificationActionTitle": {
                        "Value": {
                            "attachmentsByRange": {
                                "{0, 1}": {"Type": "ExtensionInput"},
                            },
                            "string": "\ufffc",
                        },
                        "WFSerializationType": "WFTextTokenString",
                    },
                },
            }
        ],
        "WFWorkflowInputContentItemClasses": ["WFStringContentItem"],
        "WFWorkflowTypes": ["NCWidget", "WatchKit"],
        "WFWorkflowImportQuestions": [],
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
    }
    tmp_dir = Path(tempfile.mkdtemp())
    unsigned = tmp_dir / f"{SHORTCUT_NAME}.shortcut"
    with open(unsigned, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)

    signed = tmp_dir / f"{SHORTCUT_NAME}-signed.shortcut"
    subprocess.run(
        ["shortcuts", "sign", "--mode", "anyone",
         "--input", str(unsigned), "--output", str(signed)],
        check=True,
    )
    signed.rename(unsigned)
    subprocess.run(["open", str(unsigned)], check=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} {msg}", flush=True)

# ---------------------------------------------------------------------------
# Power change handler
# ---------------------------------------------------------------------------

def _process_change() -> None:
    global _prev_connected
    info = _ioreg()
    connected = _field(info, "ExternalConnected") == "Yes"

    prev = _prev_connected
    _prev_connected = connected

    if prev is None or connected == prev:
        return

    if connected:
        watts = _adapter_int(info, "Watts") or "?"
        v_mv = _adapter_int(info, "AdapterVoltage") or 0
        c_ma = _adapter_int(info, "Current") or 0

        v_v = f"{v_mv / 1000:.0f}" if v_mv % 1000 == 0 else f"{v_mv / 1000:.1f}"
        c_a = f"{c_ma / 1000:g}"

        _notify(f"⚡ {watts}W", f"{v_v}V / {c_a}A")
        _log(f"Charger connected: {watts}W ({v_v}V / {c_a}A)")
    else:
        _log("Charger disconnected")

# ---------------------------------------------------------------------------
# IOKit callback (debounced)
# ---------------------------------------------------------------------------

def _on_power_event(_ctx: object) -> None:
    global _debounce_timer
    if _debounce_timer is not None:
        _debounce_timer.cancel()
    _debounce_timer = threading.Timer(_DEBOUNCE_SEC, _process_change)
    _debounce_timer.daemon = True
    _debounce_timer.start()

_callback_ref = _CB(_on_power_event)

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_once() -> None:
    """Print current charger info to stdout."""
    info = _ioreg()
    if _field(info, "ExternalConnected") != "Yes":
        print("No charger connected")
        return
    watts = _adapter_int(info, "Watts") or "?"
    v_mv = _adapter_int(info, "AdapterVoltage") or 0
    c_ma = _adapter_int(info, "Current") or 0
    v_v = f"{v_mv / 1000:.0f}" if v_mv % 1000 == 0 else f"{v_mv / 1000:.1f}"
    c_a = f"{c_ma / 1000:g}"
    print(f"{watts}W — {v_v}V / {c_a}A")


def cmd_install() -> None:
    """Install as a macOS LaunchAgent (auto-start on login)."""
    if not _shortcut_exists():
        print(f"'{SHORTCUT_NAME}' shortcut not found — creating it now ...")
        _setup_shortcut()
        print(f"\nPlease accept the import in the Shortcuts app,")
        print(f"then re-run:  python3 {os.path.basename(__file__)} --install")
        return

    script_path = os.path.realpath(__file__)
    python_path = _resolve_python()

    # Build PATH: include common locations for 'shortcuts' and 'ioreg'
    extra_paths = []
    for p in [
        Path.home() / ".asdf/shims",
        Path.home() / ".asdf/bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ]:
        if p.is_dir():
            extra_paths.append(str(p))
    path_env = ":".join(extra_paths + ["/usr/bin", "/bin"])

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{path_env}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/charger-watt.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/charger-watt.err</string>
</dict>
</plist>
""")
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                   capture_output=True)
    subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=True)
    print(f"LaunchAgent installed: {PLIST_PATH}")
    print(f"Python: {python_path}")
    print(f"Script: {script_path}")
    print(f"Log: /tmp/charger-watt.log")


def cmd_uninstall() -> None:
    """Remove the LaunchAgent."""
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                   capture_output=True)
    PLIST_PATH.unlink(missing_ok=True)
    print("LaunchAgent uninstalled")


def cmd_monitor() -> None:
    """Start the event-driven monitor (blocks forever)."""
    global _prev_connected
    info = _ioreg()
    _prev_connected = _field(info, "ExternalConnected") == "Yes"
    state = "charger connected" if _prev_connected else "on battery"
    _log(f"charger-watt monitor started (IOKit event-driven)")
    _log(f"Current state: {state}")

    source = _iokit.IOPSNotificationCreateRunLoopSource(_callback_ref, None)
    if not source:
        _log("Error: failed to create power event listener")
        sys.exit(1)

    _cf.CFRunLoopAddSource(
        _cf.CFRunLoopGetCurrent(), source, _kCFRunLoopDefaultMode,
    )
    _cf.CFRunLoopRun()


def cmd_help() -> None:
    print("""\
Usage: charger-watt [option]

Show a macOS notification banner with charger wattage when plugged in.
Event-driven via IOKit — zero polling.

Options:
    (none)          Start the event monitor (foreground)
    --once          Print current charger info and exit
    --install       Install as a LaunchAgent (auto-start on login)
    --uninstall     Remove the LaunchAgent
    --help, -h      Show this help message""")


if __name__ == "__main__":
    args = set(sys.argv[1:])
    if args & {"--help", "-h"}:
        cmd_help()
    elif "--once" in args:
        cmd_once()
    elif "--install" in args:
        cmd_install()
    elif "--uninstall" in args:
        cmd_uninstall()
    else:
        cmd_monitor()
