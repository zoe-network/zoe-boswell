#!/usr/bin/env python3
"""Post-meeting field report generator.

Reads a transcript and produces a structured field report using
a local or remote LLM via OpenAI-compatible API.

Usage:
    python -m boswell.report                                   # latest transcript
    python -m boswell.report --transcript path/to/transcript.log
    python -m boswell.report --title "Discovery Call"
    python -m boswell.report --attendees "Alice,Bob"
"""

import argparse
import datetime
import os
import sys
from pathlib import Path

import yaml

from boswell import context as ctx
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


def extract_session(transcript_path: Path) -> str:
    if not transcript_path.exists():
        return ""
    text = transcript_path.read_text()
    sessions = text.split("--- session ")
    if len(sessions) < 2:
        return text
    return "--- session " + sessions[-1]


def generate_report(transcript: str, meeting_context: str, config: dict, api_key: str) -> str:
    import requests

    endpoint = config.get("model", {}).get("endpoint", "")
    model = config.get("report", {}).get("model",
            config.get("model", {}).get("name", "granite3.2:8b"))

    user_msg = f"""MEETING CONTEXT:
{meeting_context}

FULL TRANSCRIPT:
{transcript[:12000]}

Generate the field report."""

    resp = requests.post(
        f"{endpoint}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": prompts.report(config)},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 2000,
            "temperature": 0.2,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def main():
    parser = argparse.ArgumentParser(description="Boswell — post-meeting field report")
    parser.add_argument("--config", help="Path to config.yaml")
    parser.add_argument("--transcript", help="Transcript file path")
    parser.add_argument("--title", default="", help="Meeting title for filename")
    parser.add_argument("--attendees", help="Comma-separated attendee names")
    parser.add_argument("--output-dir", default="./field-reports", help="Report output directory")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt without calling model")
    args = parser.parse_args()

    config = load_config(args.config)
    api_key = get_api_key(config)

    if not api_key and not args.dry_run:
        print("ERROR: No API key. Set key_file in config.yaml or BOSWELL_API_KEY env var.",
              file=sys.stderr)
        sys.exit(1)

    transcript_path = Path(
        args.transcript or config.get("transcript", {}).get("path", "transcript.log")
    ).expanduser()

    transcript = extract_session(transcript_path)
    if not transcript.strip():
        print("ERROR: No transcript content found.", file=sys.stderr)
        sys.exit(1)

    attendee_names = [n.strip() for n in args.attendees.split(",")] if args.attendees else []
    meeting_context = ctx.build_context(config, attendee_names)

    report_model = config.get("report", {}).get("model",
                   config.get("model", {}).get("name", "granite3.2:8b"))
    print(f"[boswell-report] Model: {report_model}")
    print(f"[boswell-report] Transcript: {len(transcript)} chars from {transcript_path}")

    if args.dry_run:
        print(f"[dry-run] Would send {len(transcript[:12000])} chars transcript + {len(meeting_context)} chars context")
        return

    report_text = generate_report(transcript, meeting_context, config, api_key)

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    title_slug = args.title.lower().replace(" ", "-").replace("/", "-")[:40] if args.title else "meeting"
    filename = f"FR-{date_str}-{title_slug}.md"
    output_path = output_dir / filename

    full_report = f"""---
date: {date_str}
title: {args.title or 'Meeting Notes'}
attendees: {', '.join(attendee_names) if attendee_names else 'unknown'}
model: {report_model}
source: {transcript_path}
---

# Field Report: {args.title or 'Meeting Notes'}
**Date:** {date_str}

{report_text}
"""

    output_path.write_text(full_report)
    print(f"[boswell-report] Written to {output_path}")


if __name__ == "__main__":
    main()
