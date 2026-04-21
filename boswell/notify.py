#!/usr/bin/env python3
"""Desktop and terminal notifications."""

import subprocess
import sys
import textwrap


def notify_desktop(title: str, body: str, urgency: str = "normal", timeout: int = 10):
    cmd = [
        "notify-send",
        "--urgency", urgency,
        "--expire-time", str(timeout * 1000),
        "--app-name", "Boswell",
        title,
        body,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"[notify] desktop notification failed: {e}", file=sys.stderr)


def notify_terminal(title: str, body: str):
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("-" * width)
    for line in body.splitlines():
        for wrapped in textwrap.wrap(line, width - 4):
            print(f"  {wrapped}")
    print("=" * width)
    print()
    sys.stdout.flush()


def send(title: str, body: str, config: dict):
    mode = config.get("notify", {}).get("mode", "both")
    urgency = config.get("notify", {}).get("urgency", "normal")
    timeout = config.get("notify", {}).get("timeout", 10)

    if mode in ("terminal", "both"):
        notify_terminal(title, body)
    if mode in ("desktop", "both"):
        notify_desktop(title, body, urgency=urgency, timeout=timeout)
