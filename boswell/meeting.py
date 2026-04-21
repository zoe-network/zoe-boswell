#!/usr/bin/env python3
"""Boswell Meeting — single-window meeting intelligence.

Combines Capture (Whisper transcription) with optional real-time Advisory
and post-meeting field report generation. Everything in one scrolling window.

Usage:
    python -m boswell                                     # auto-detect, defaults
    python -m boswell --model base.en                     # smaller/faster STT
    python -m boswell --attendees "Alice,Bob"              # context-aware advisory
    python -m boswell --mode internal                      # internal meeting prompts
    python -m boswell --briefing prep.md                   # inject meeting prep
    python -m boswell --no-advisory                        # transcript only
"""

import argparse
import datetime
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import yaml

from boswell import context as ctx
from boswell import prompts
from boswell.report import generate_report, load_config as load_report_config

SAMPLE_RATE = 16000
NATIVE_RATE = 48000
NATIVE_CHANNELS = 2
CHUNK_SECONDS = 10
SILENCE_THRESHOLD = 200
DEFAULT_STT_MODEL = "base.en"

COLORS = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "cyan": "\033[36m",
    "yellow": "\033[33m",
    "green": "\033[32m",
    "magenta": "\033[35m",
    "red": "\033[31m",
}


def c(color, text):
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def list_sources():
    result = subprocess.run(
        ["pactl", "list", "short", "sources"],
        capture_output=True, text=True
    )
    print(result.stdout)


def find_audio_source():
    result = subprocess.run(
        ["pactl", "list", "short", "sources"],
        capture_output=True, text=True
    )
    for line in result.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 2 and "whisper_mix.monitor" in parts[1]:
            return parts[1]
    for line in result.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 2 and ".monitor" in parts[1] and "RUNNING" in line:
            return parts[1]
    return None


def record_chunk(source, duration):
    from scipy.signal import resample

    frame_size = NATIVE_CHANNELS * 4
    expected_bytes = int(NATIVE_RATE * duration * frame_size)

    cmd = [
        "parec",
        "--device", source,
        "--format", "float32le",
        "--channels", str(NATIVE_CHANNELS),
        "--rate", str(NATIVE_RATE),
        "--latency-msec", "100",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    raw = proc.stdout.read(expected_bytes)
    proc.terminate()
    proc.wait()

    if len(raw) < frame_size * 100:
        return None

    audio = np.frombuffer(raw, dtype=np.float32)
    mono = audio[0::NATIVE_CHANNELS]
    target_samples = int(len(mono) * SAMPLE_RATE / NATIVE_RATE)
    resampled = resample(mono, target_samples).astype(np.float32)
    return resampled


def is_silence_f32(audio_f32):
    if audio_f32 is None or len(audio_f32) < 100:
        return True
    rms = np.sqrt(np.mean((audio_f32 * 32768) ** 2))
    return rms < SILENCE_THRESHOLD


def call_advisory(transcript_lines, meeting_context, config, api_key, system_prompt):
    import requests

    endpoint = config.get("model", {}).get("endpoint", "")
    model = config.get("model", {}).get("name", "granite3.2:8b")
    max_tokens = config.get("model", {}).get("max_tokens", 300)

    chunk = "\n".join(transcript_lines[-40:])

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
                {"role": "user", "content": f"CONTEXT:\n{meeting_context}\n\nTRANSCRIPT:\n{chunk}\n\nAdvise:"},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def print_header(source, stt_model, advisory_model, attendees):
    width = 60
    print(c("cyan", "-" * width))
    print(c("cyan", "  Boswell"))
    print(c("dim", f"  Audio: {source}"))
    print(c("dim", f"  STT: {stt_model} | Advisory: {advisory_model}"))
    if attendees:
        print(c("dim", f"  Attendees: {', '.join(attendees)}"))
    print(c("cyan", "-" * width))
    print(c("dim", "  Listening... tips appear inline."))
    print(c("dim", "  Ctrl+C to stop and generate field report."))
    print(c("cyan", "-" * width))
    print()


def print_transcript(ts, text):
    print(f"  {c('dim', ts)}  {text}")
    sys.stdout.flush()


def print_tip(text):
    print()
    print(f"  {c('yellow', '>')} {c('bold', text)}")
    print()
    sys.stdout.flush()


class AdvisoryThread(threading.Thread):
    def __init__(self, config, api_key, meeting_context, interval=30, min_new=3, system_prompt=""):
        super().__init__(daemon=True)
        self.config = config
        self.api_key = api_key
        self.meeting_context = meeting_context
        self.system_prompt = system_prompt
        self.interval = interval
        self.min_new = min_new
        self.transcript_lines = []
        self.last_advised_count = 0
        self.lock = threading.Lock()
        self.running = True

    def add_line(self, line):
        with self.lock:
            self.transcript_lines.append(line)

    def run(self):
        while self.running:
            time.sleep(self.interval)
            with self.lock:
                current_count = len(self.transcript_lines)
                new_count = current_count - self.last_advised_count
                if new_count < self.min_new:
                    continue
                lines_copy = list(self.transcript_lines)
                self.last_advised_count = current_count

            try:
                response = call_advisory(
                    lines_copy, self.meeting_context, self.config,
                    self.api_key, self.system_prompt
                )
                if response.strip().upper() != "PASS":
                    tip = response
                    if tip.upper().startswith("TIP:"):
                        tip = tip[4:].strip()
                    print_tip(tip)
            except Exception as e:
                print(f"  {c('red', f'[advisory error: {e}]')}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Boswell — sovereign meeting intelligence")
    parser.add_argument("--source", help="PulseAudio/PipeWire source name")
    parser.add_argument("--list-sources", action="store_true")
    parser.add_argument("--model", default=DEFAULT_STT_MODEL, help="Whisper model (default: base.en)")
    parser.add_argument("--attendees", help="Comma-separated attendee names")
    parser.add_argument("--config", help="Path to config.yaml")
    parser.add_argument("--chunk", type=int, default=CHUNK_SECONDS, help="Chunk duration seconds")
    parser.add_argument("--mode", choices=["customer", "internal"], default="customer")
    parser.add_argument("--briefing", help="Path to meeting briefing/prep file")
    parser.add_argument("--no-advisory", action="store_true", help="Transcript only, no model calls")
    args = parser.parse_args()

    if args.list_sources:
        list_sources()
        return

    config_path = Path(args.config) if args.config else Path("config.yaml")
    config = {}
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)

    source = args.source or find_audio_source()
    if not source:
        print("ERROR: No audio source found. Use --list-sources or --source.", file=sys.stderr)
        sys.exit(1)

    api_key = ""
    if not args.no_advisory:
        key_file_path = config.get("model", {}).get("key_file", "")
        if key_file_path:
            key_file = Path(key_file_path).expanduser()
            if key_file.exists():
                api_key = key_file.read_text().strip()
        if not api_key:
            api_key = os.environ.get("BOSWELL_API_KEY", "")
        endpoint = config.get("model", {}).get("endpoint", "")
        if not api_key and "localhost" not in endpoint and "127.0.0.1" not in endpoint:
            print("WARNING: No API key and non-local endpoint — transcript-only mode.", file=sys.stderr)
            args.no_advisory = True

    attendee_names = [n.strip() for n in args.attendees.split(",")] if args.attendees else []
    meeting_context = ctx.build_context(config, attendee_names) if not args.no_advisory else ""

    if args.briefing:
        briefing_path = Path(args.briefing).expanduser()
        if briefing_path.exists():
            briefing_text = briefing_path.read_text()
            if briefing_path.suffix == ".html":
                briefing_text = re.sub(r'<style[^>]*>.*?</style>', '', briefing_text, flags=re.DOTALL)
                briefing_text = re.sub(r'<[^>]+>', ' ', briefing_text)
                briefing_text = re.sub(r'\s+', ' ', briefing_text).strip()
            meeting_context = f"MEETING BRIEFING:\n{briefing_text}\n\n{meeting_context}"
            print(c("green", f"  Briefing loaded: {briefing_path} ({len(briefing_text)} chars)"))
        else:
            print(c("red", f"  Briefing not found: {briefing_path}"), file=sys.stderr)

    if args.mode == "internal":
        system_prompt = prompts.advisory_internal(config)
    else:
        system_prompt = prompts.advisory_customer(config)

    advisory_model = config.get("model", {}).get("name", "granite3.2:8b")
    print_header(source, args.model, advisory_model, attendee_names)

    print(c("dim", "  Loading STT model..."), end=" ", flush=True)
    from faster_whisper import WhisperModel
    whisper = WhisperModel(args.model, device="cpu", compute_type="int8")
    print(c("green", "ready."))
    print()

    log_path = Path("transcript.log")

    advisor = None
    if not args.no_advisory:
        interval = config.get("transcript", {}).get("interval_seconds", 30)
        min_new = config.get("transcript", {}).get("min_new_lines", 3)
        advisor = AdvisoryThread(config, api_key, meeting_context, interval, min_new, system_prompt)
        advisor.start()

    all_lines = []
    running = True

    def handle_sig(sig, frame):
        nonlocal running
        running = False
        print(f"\n{c('cyan', '  Stopping...')}")

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    session_start = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(log_path, "a") as f:
        f.write(f"\n--- session {session_start} ---\n")

        while running:
            audio = record_chunk(source, args.chunk)

            if is_silence_f32(audio):
                continue

            segments, _ = whisper.transcribe(audio, language="en", vad_filter=True)

            for seg in segments:
                ts = datetime.datetime.now(datetime.UTC).strftime("%H:%M:%S")
                text = seg.text.strip()
                if not text:
                    continue

                line = f"[{ts}] {text}"
                print_transcript(ts, text)
                all_lines.append(line)

                f.write(line + "\n")
                f.flush()

                if advisor:
                    advisor.add_line(line)

    if advisor:
        advisor.running = False

    print()
    print(c("cyan", "-" * 60))
    print(c("cyan", f"  Session ended. {len(all_lines)} lines transcribed."))

    if all_lines and not args.no_advisory:
        print(c("dim", "  Generating field report..."))
        try:
            report_config = load_report_config(args.config)
            report_text = generate_report(
                "\n".join(all_lines),
                meeting_context,
                report_config,
                api_key,
            )
            output_dir = Path(config.get("report", {}).get("output_dir", "./field-reports")).expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            filename = f"FR-{date_str}-meeting.md"
            output_path = output_dir / filename

            full_report = f"""---
date: {date_str}
attendees: {', '.join(attendee_names) if attendee_names else 'unknown'}
model: {report_config.get('report', {}).get('model', 'granite3.2:8b')}
---

# Field Report
**Date:** {date_str}

{report_text}
"""
            output_path.write_text(full_report)
            print(c("green", f"  Report: {output_path}"))
        except Exception as e:
            print(c("red", f"  Report generation failed: {e}"))

    print(c("cyan", "-" * 60))


if __name__ == "__main__":
    main()
