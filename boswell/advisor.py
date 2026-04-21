#!/usr/bin/env python3
"""Boswell Advisor — real-time meeting intelligence.

Tails the transcript log, sends chunks to a local LLM with
meeting context, and surfaces actionable tips via desktop notifications.

This is the "tail sniffer" — it watches what Capture writes and
whispers advice in real time. Optional, not required for transcription.

Usage:
    python -m boswell.advisor                                  # default config
    python -m boswell.advisor --attendees "Alice,Bob"          # context-aware
    python -m boswell.advisor --context extra-brief.md         # inject context
    python -m boswell.advisor --dry-run                        # print prompts only
"""

import argparse
import datetime
import os
import sys
import time
from pathlib import Path

import yaml

from boswell import context as ctx
from boswell import notify
from boswell import prompts


def load_config(path: str = None) -> dict:
    config_path = Path(path) if path else Path("config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def get_api_key(config: dict) -> str:
    key_path = config.get("model", {}).get("key_file", "")
    if not key_path:
        return os.environ.get("BOSWELL_API_KEY", "no-key-needed")
    key_file = Path(key_path).expanduser()
    if key_file.is_file():
        return key_file.read_text().strip()
    return os.environ.get("BOSWELL_API_KEY", "no-key-needed")


def tail_file(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    return lines[-n:]


def call_model(transcript_chunk: str, meeting_context: str,
               config: dict, api_key: str, system_prompt: str) -> str:
    import requests

    endpoint = config.get("model", {}).get("endpoint", "")
    model = config.get("model", {}).get("name", "granite3.2:8b")
    max_tokens = config.get("model", {}).get("max_tokens", 300)

    user_msg = f"""MEETING CONTEXT:
{meeting_context}

RECENT TRANSCRIPT:
{transcript_chunk}

What should the user know or do right now?"""

    resp = requests.post(
        f"{endpoint}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def main():
    parser = argparse.ArgumentParser(description="Boswell Advisor — real-time meeting intelligence")
    parser.add_argument("--config", help="Path to config.yaml")
    parser.add_argument("--model", help="Override model name")
    parser.add_argument("--attendees", help="Comma-separated attendee names")
    parser.add_argument("--context", action="append", default=[], help="Extra context file(s)")
    parser.add_argument("--mode", choices=["customer", "internal"], default="customer")
    parser.add_argument("--transcript", help="Override transcript log path")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without calling model")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.model:
        config.setdefault("model", {})["name"] = args.model
    if os.environ.get("BOSWELL_MODEL"):
        config.setdefault("model", {})["name"] = os.environ["BOSWELL_MODEL"]
    if args.context:
        config.setdefault("context", {}).setdefault("extra", []).extend(args.context)

    api_key = get_api_key(config)
    endpoint = config.get("model", {}).get("endpoint", "")
    if not api_key and not args.dry_run and "localhost" not in endpoint and "127.0.0.1" not in endpoint:
        print("ERROR: No API key. Set key_file in config.yaml or BOSWELL_API_KEY env var.",
              file=sys.stderr)
        sys.exit(1)

    transcript_path = Path(
        args.transcript or config.get("transcript", {}).get("path", "transcript.log")
    ).expanduser()

    tail_lines = config.get("transcript", {}).get("tail_lines", 40)
    interval = config.get("transcript", {}).get("interval_seconds", 30)
    min_new = config.get("transcript", {}).get("min_new_lines", 3)

    attendee_names = [n.strip() for n in args.attendees.split(",")] if args.attendees else []
    meeting_context = ctx.build_context(config, attendee_names)

    if args.mode == "internal":
        system_prompt = prompts.advisory_internal(config)
    else:
        system_prompt = prompts.advisory_customer(config)

    model_name = config.get("model", {}).get("name", "granite3.2:8b")
    print(f"[boswell-advisor] Model: {model_name}")
    print(f"[boswell-advisor] Transcript: {transcript_path}")
    print(f"[boswell-advisor] Interval: {interval}s, min new lines: {min_new}")
    if attendee_names:
        print(f"[boswell-advisor] Attendees: {', '.join(attendee_names)}")
    print(f"[boswell-advisor] Context: {len(meeting_context)} chars")
    print(f"[boswell-advisor] Watching... (Ctrl+C to stop)")
    print()

    last_line_count = 0
    if transcript_path.exists():
        last_line_count = len(transcript_path.read_text().splitlines())

    try:
        while True:
            time.sleep(interval)

            if not transcript_path.exists():
                continue

            current_lines = transcript_path.read_text().splitlines()
            new_count = len(current_lines) - last_line_count

            if new_count < min_new:
                continue

            last_line_count = len(current_lines)
            chunk = "\n".join(current_lines[-tail_lines:])

            if args.dry_run:
                print(f"[dry-run] Would send {len(chunk)} chars transcript + {len(meeting_context)} chars context")
                continue

            try:
                response = call_model(chunk, meeting_context, config, api_key, system_prompt)
            except Exception as e:
                print(f"[boswell-advisor] Model call failed: {e}", file=sys.stderr)
                continue

            if response.strip().upper() == "PASS":
                continue

            tip = response
            if tip.upper().startswith("TIP:"):
                tip = tip[4:].strip()

            ts = datetime.datetime.now().strftime("%H:%M")
            notify.send(f"Boswell [{ts}]", tip, config)

    except KeyboardInterrupt:
        print("\n[boswell-advisor] Stopped.")


if __name__ == "__main__":
    main()
