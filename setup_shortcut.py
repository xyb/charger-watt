#!/usr/bin/env python3
"""Create and import the "charger-watt" shortcut for macOS notification banners.

The shortcut accepts text via stdin and shows it as a system notification.
charger-watt uses this shortcut to display charger info.

Run once:  python3 setup_shortcut.py
"""
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path

SHORTCUT_NAME = "Charger Watt"


def create_shortcut() -> Path:
    """Build a .shortcut plist that shows input text as a notification."""
    shortcut = {
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 4274264319,   # yellow
            "WFWorkflowIconGlyphNumber": 59764,        # lightningBolt
        },
        "WFWorkflowActions": [
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
                "WFWorkflowActionParameters": {
                    "WFNotificationActionBody": "",
                    "WFNotificationActionTitle": {
                        "Value": {
                            "attachmentsByRange": {
                                "{0, 1}": {
                                    "Type": "ExtensionInput",
                                },
                            },
                            "string": "\ufffc",
                        },
                        "WFSerializationType": "WFTextTokenString",
                    },
                },
            }
        ],
        "WFWorkflowInputContentItemClasses": [
            "WFStringContentItem",
        ],
        "WFWorkflowTypes": ["NCWidget", "WatchKit"],
        "WFWorkflowImportQuestions": [],
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
    }
    tmp = Path(tempfile.mkdtemp()) / f"{SHORTCUT_NAME}.shortcut"
    with open(tmp, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)
    return tmp


def sign_and_import(unsigned: Path) -> None:
    signed = unsigned.parent / f"{SHORTCUT_NAME}-signed.shortcut"
    subprocess.run(
        ["shortcuts", "sign", "--mode", "anyone",
         "--input", str(unsigned), "--output", str(signed)],
        check=True,
    )

    final = unsigned.parent / f"{SHORTCUT_NAME}.shortcut"
    signed.rename(final)

    subprocess.run(["open", str(final)], check=True)
    print(f"The Shortcuts app should now prompt you to import '{SHORTCUT_NAME}'.")
    print("Accept the import, then run:  python3 charger_watt.py --install")


def main() -> None:
    r = subprocess.run(["shortcuts", "list"], capture_output=True, text=True)
    if SHORTCUT_NAME in r.stdout.splitlines():
        print(f"'{SHORTCUT_NAME}' shortcut already exists. Nothing to do.")
        sys.exit(0)

    print(f"Creating '{SHORTCUT_NAME}' shortcut ...")
    path = create_shortcut()
    sign_and_import(path)


if __name__ == "__main__":
    main()
