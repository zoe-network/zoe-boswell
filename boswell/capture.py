#!/usr/bin/env python3
"""Boswell Capture — real-time meeting transcription via PipeWire + faster-whisper.

Captures system audio from any PipeWire/PulseAudio source, chunks it,
transcribes locally with Whisper. Your hardware, your model, your transcript.

Usage:
    python -m boswell.capture                  # auto-detect system audio
    python -m boswell.capture --gpu            # use GPU if available
    python -m boswell.capture --source NAME    # specific PulseAudio source
    python -m boswell.capture --list-sources   # show available sources
    python -m boswell.capture --file out.txt   # custom output path
"""

import argparse
import collections
import datetime
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SECONDS = 24
SILENCE_THRESHOLD = 200
MODEL_SIZE = "medium.en"
DEFAULT_TRANSCRIPT = Path("transcript.log")


def list_sources():
    result = subprocess.run(
        ["pactl", "list", "short", "sources"],
        capture_output=True, text=True
    )
    print(result.stdout)


def find_monitor_source():
    """Find the first running .monitor source, or fall back to first available."""
    result = subprocess.run(
        ["pactl", "list", "short", "sources"],
        capture_output=True, text=True
    )
    monitors = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 2 and ".monitor" in parts[1]:
            monitors.append((parts[1], "RUNNING" in line))

    for name, running in monitors:
        if running:
            return name
    if monitors:
        return monitors[0][0]
    return None


def preflight_checks():
    """Warn about resource contention. Returns True if safe to proceed."""
    warnings = []

    try:
        result = subprocess.run(
            ["pw-cli", "list-objects", "Node"],
            capture_output=True, text=True
        )
        active_streams = []
        lines = result.stdout.split("\n")
        for i, line in enumerate(lines):
            if "media.class" in line and "Stream/Output/Audio" in line:
                for j in range(max(0, i - 10), i):
                    if "node.name" in lines[j]:
                        name = lines[j].split("=")[-1].strip().strip('"')
                        active_streams.append(name)
                        break
        if active_streams:
            warnings.append(
                f"  - Active audio playback: {', '.join(active_streams[:3])}\n"
                f"    Tapping the monitor source may cause audio glitches."
            )
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    if warnings:
        print("[boswell] PRE-FLIGHT WARNINGS:", file=sys.stderr)
        for w in warnings:
            print(w, file=sys.stderr)
        print(file=sys.stderr)
        try:
            answer = input("[boswell] Continue anyway? (y/N) ")
            if answer.lower() != "y":
                print("[boswell] Aborted.")
                return False
        except EOFError:
            print("[boswell] Non-interactive — aborting due to warnings.", file=sys.stderr)
            return False

    return True


def audio_to_numpy(raw_bytes):
    audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


def is_silence(raw_bytes, threshold=SILENCE_THRESHOLD):
    if len(raw_bytes) < 100:
        return True
    audio = np.frombuffer(raw_bytes, dtype=np.int16)
    rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
    return rms < threshold


def main():
    parser = argparse.ArgumentParser(description="Boswell Capture — sovereign meeting transcription")
    parser.add_argument("--source", help="PulseAudio source name")
    parser.add_argument("--list-sources", action="store_true", help="List audio sources and exit")
    parser.add_argument("--file", type=Path, default=DEFAULT_TRANSCRIPT, help="Transcript output file")
    parser.add_argument("--model", default=MODEL_SIZE, help="Whisper model size (default: medium.en)")
    parser.add_argument("--chunk", type=int, default=CHUNK_SECONDS, help="Chunk duration in seconds")
    parser.add_argument("--gpu", action="store_true", help="Use GPU for inference (default: CPU)")
    parser.add_argument("--skip-checks", action="store_true", help="Skip pre-flight safety checks")
    args = parser.parse_args()

    if args.list_sources:
        list_sources()
        return

    if not args.skip_checks:
        if not preflight_checks():
            sys.exit(1)

    source = args.source or find_monitor_source()
    if not source:
        print("ERROR: No audio monitor source found. Use --list-sources.", file=sys.stderr)
        sys.exit(1)

    device = "cuda" if args.gpu else "cpu"
    compute_type = "float16" if args.gpu else "int8"

    print(f"[boswell] Loading model: {args.model} (device={device})")
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device=device, compute_type=compute_type)

    print(f"[boswell] Source: {source}")
    print(f"[boswell] Chunk: {args.chunk}s")
    print(f"[boswell] Transcript: {args.file}")
    print(f"[boswell] Listening... (Ctrl+C to stop)")
    print()

    args.file.parent.mkdir(parents=True, exist_ok=True)

    running = True

    def handle_sig(sig, frame):
        nonlocal running
        running = False
        print("\n[boswell] Stopping...")

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    bytes_per_sec = SAMPLE_RATE * 2
    chunk_bytes = args.chunk * bytes_per_sec
    buffer = collections.deque()
    buf_lock = threading.Lock()

    parec = subprocess.Popen(
        ["parec", "--device", source, "--format", "s16le",
         "--channels", "1", "--rate", str(SAMPLE_RATE), "--latency-msec", "100"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )

    def reader():
        while running:
            data = parec.stdout.read(bytes_per_sec)
            if not data:
                break
            with buf_lock:
                buffer.append(data)
    t = threading.Thread(target=reader, daemon=True)
    t.start()

    def take_chunk():
        with buf_lock:
            total = sum(len(b) for b in buffer)
            if total < chunk_bytes:
                return None
            out = bytearray()
            while buffer and len(out) < chunk_bytes:
                out.extend(buffer.popleft())
            return bytes(out)

    with open(args.file, "a") as f:
        f.write(f"\n--- session {datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')} ---\n")

        while running:
            raw = take_chunk()
            if raw is None:
                time.sleep(0.5)
                continue

            if is_silence(raw):
                continue

            audio = audio_to_numpy(raw)
            segments, _ = model.transcribe(
                audio, language="en", vad_filter=False,
                condition_on_previous_text=True, beam_size=5,
                no_speech_threshold=0.2, log_prob_threshold=-1.5,
                compression_ratio_threshold=2.8,
            )

            text = " ".join(s.text.strip() for s in segments).strip()
            if not text:
                continue
            ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
            line = f"[{ts}] {text}"
            print(line)
            f.write(line + "\n")
            f.flush()

        parec.terminate()


if __name__ == "__main__":
    main()
