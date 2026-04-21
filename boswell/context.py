#!/usr/bin/env python3
"""Build meeting context from calendar, memory, and extra files."""

import datetime
from pathlib import Path


def load_calendar(calendar_path: str) -> list[dict]:
    path = Path(calendar_path).expanduser()
    if not path.exists():
        return []

    events = []
    current = None
    for line in path.read_text().splitlines():
        if line.startswith("## ") or line.startswith("### "):
            if current:
                events.append(current)
            current = {"raw": line.strip("# ").strip(), "details": []}
        elif current and line.strip():
            current["details"].append(line.strip())

    if current:
        events.append(current)
    return events


def find_current_meeting(calendar_path: str) -> str | None:
    events = load_calendar(calendar_path)
    if not events:
        return None

    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    today_events = []
    for ev in events:
        if today_str in ev["raw"] or now.strftime("%A") in ev["raw"]:
            today_events.append(ev)

    if not today_events:
        return None

    lines = ["Today's meetings:"]
    for ev in today_events:
        lines.append(f"  {ev['raw']}")
        for d in ev["details"][:5]:
            lines.append(f"    {d}")
    return "\n".join(lines)


def scan_memory_for_attendees(memory_dir: str, attendee_names: list[str]) -> str:
    mdir = Path(memory_dir).expanduser()
    if not mdir.exists():
        return ""

    hits = []
    for md_file in mdir.glob("*.md"):
        content = md_file.read_text()
        for name in attendee_names:
            if name.lower() in content.lower():
                lines = content.splitlines()
                desc = ""
                for line in lines:
                    if line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip()
                        break
                hits.append(f"[{md_file.name}] {desc}: mentions {name}")
                break

    return "\n".join(hits) if hits else ""


def build_context(config: dict, attendee_names: list[str] | None = None) -> str:
    parts = []

    cal_path = config.get("context", {}).get("calendar", "")
    if cal_path:
        meeting_info = find_current_meeting(cal_path)
        if meeting_info:
            parts.append(meeting_info)

    if attendee_names:
        mem_dir = config.get("context", {}).get("memory_dir", "")
        if mem_dir:
            mem_hits = scan_memory_for_attendees(mem_dir, attendee_names)
            if mem_hits:
                parts.append(f"Relevant memory:\n{mem_hits}")

    for extra_path in config.get("context", {}).get("extra", []):
        p = Path(extra_path).expanduser()
        if p.exists():
            parts.append(f"--- {p.name} ---\n{p.read_text()[:2000]}")

    return "\n\n".join(parts) if parts else "No additional context available."
