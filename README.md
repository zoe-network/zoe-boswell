# Boswell

**Same meetings. Better outcomes.**

Boswell captures any audio stream on your Linux desktop — Google Meet, Zoom, Teams, a phone call on speaker, a podcast, anything PipeWire can route — and transcribes it locally using [faster-whisper](https://github.com/SYSTRAN/faster-whisper). No cloud. No subscription. No one else's server touching your audio.

The transcript is yours. It stays on your disk. What you do with it after that is up to you.

Part of the [Zoe](https://github.com/zoe-network) project.

## What it does

**Capture.** Real-time speech-to-text from any audio source on your desktop. Whisper runs locally — CPU or GPU. Timestamped transcript streams to your terminal and appends to a log file. Works with any meeting platform, any audio stream, any language Whisper supports.

**Summarize.** After a meeting ends, Boswell generates a structured field report — summary, key decisions, action items, technical discussion, raw quotes — using a local LLM via any OpenAI-compatible API. Default is [Ollama](https://ollama.com) with Granite, but any model works.

**Advise.** Optionally, Boswell can tail the transcript in real time and surface tips via desktop notifications while the meeting is running — a local agent watching the conversation and whispering when something is worth noting. This is experimental and entirely optional.

## Requirements

- **Linux** with PipeWire (ships default on Fedora 34+, Ubuntu 22.10+, RHEL 9+)
- **Python 3.10+**
- **PulseAudio utilities** (`pactl`, `parec` — installed by default on most PipeWire systems)
- **Ollama** (or any OpenAI-compatible LLM endpoint) for summarization

### Hardware

| | Capture only | Capture + Report | Capture + Live Advisory |
|---|---|---|---|
| **What runs** | Whisper (STT) | Whisper, then LLM | Whisper + LLM concurrently |
| **RAM** | 2 GB (`base.en`) / 4 GB (`medium.en`) | 8 GB | 16 GB+ |
| **CPU** | Any modern x86_64 | 8+ cores recommended | 8+ cores |
| **GPU** | Optional (speeds up Whisper) | Optional | Recommended (NVIDIA + CUDA) |
| **Disk** | ~1 GB for models | ~6 GB (Whisper + Granite 8B) | ~6 GB |

Whisper model sizes: `base.en` (~150 MB, fast, decent) through `large-v3` (~3 GB, slow on CPU, excellent). Default for capture-only is `medium.en` — the sweet spot for accuracy vs. speed on CPU. Default for combined mode is `base.en` for responsiveness.

**Reference platform** (where Boswell was built and tested):

| | |
|---|---|
| OS | Red Hat Enterprise Linux 10.1 |
| CPU | AMD Ryzen 9 3900X — 12 cores / 24 threads |
| RAM | 32 GB |
| GPU | NVIDIA GeForce RTX 3070 — 8 GB VRAM |
| CUDA | 13.0 |
| Python | 3.12 |

All three modes run comfortably on this machine. Capture + live advisory with `medium.en` on GPU leaves room to spare.

## Quick start

```bash
# Clone
git clone https://github.com/zoe-network/zoe-boswell.git
cd zoe-boswell

# Install dependencies
pip install -r requirements.txt

# Copy and edit config
cp config.example.yaml config.yaml

# Check your audio sources
python -m boswell.capture --list-sources

# Start transcribing (transcript-only, no LLM needed)
python -m boswell.capture
```

That's it. Audio in, text out. The transcript appends to `transcript.log` in the current directory.

## Modes

### Capture only (no LLM required)

```bash
python -m boswell.capture                    # auto-detect audio source
python -m boswell.capture --gpu              # use GPU for faster inference
python -m boswell.capture --model large-v3   # bigger model, better accuracy
python -m boswell.capture --source NAME      # specific PulseAudio source
```

Whisper is a speech-to-text model, not an LLM. It converts audio to text — that's all. It runs entirely on your CPU (or GPU with `--gpu`). No network calls, no API keys, no cloud anything.

### Combined mode (capture + summarize + optional advisory)

```bash
python -m boswell                             # auto-detect everything
python -m boswell --attendees "Alice,Bob"     # context-aware
python -m boswell --mode internal             # internal meeting prompts
python -m boswell --briefing prep.md          # inject meeting prep context
python -m boswell --no-advisory               # transcribe + report, no real-time tips
```

Combined mode runs Whisper for transcription and an LLM for summarization in a single window. When you hit Ctrl+C, Boswell generates a field report from the full transcript.

### Post-meeting report (from existing transcript)

```bash
python -m boswell.report                                     # latest session
python -m boswell.report --transcript path/to/transcript.log
python -m boswell.report --title "Q3 Planning"
python -m boswell.report --attendees "Alice,Bob"
```

### Advisory only (tail an existing transcript)

```bash
python -m boswell.advisor                    # watch transcript.log
python -m boswell.advisor --mode internal    # internal meeting tips
python -m boswell.advisor --dry-run          # see prompts without calling model
```

## Audio routing

Boswell captures from PipeWire/PulseAudio monitor sources. Out of the box, it auto-detects the first running `.monitor` source — which is usually your desktop audio output.

### Dedicated capture sink (recommended)

Create a virtual sink so Boswell captures meeting audio without affecting your speakers:

```bash
# Create a virtual sink
pactl load-module module-null-sink sink_name=whisper_mix sink_properties=device.description="Whisper-Mix"

# Route your meeting app's audio to this sink (use pavucontrol or pw-link)
# Boswell auto-detects whisper_mix.monitor when it exists
```

### Verify sources

```bash
python -m boswell.capture --list-sources
```

## Configuration

Copy `config.example.yaml` to `config.yaml`:

```yaml
user:
  name: "Your Name"
  role: "Your Role"
  org: "Your Org"

model:
  endpoint: "http://localhost:11434/v1"    # Ollama default
  name: "granite3.2:8b"                    # any Ollama model
  key_file: ""                             # blank for Ollama
```

The `user` section personalizes the advisory and report prompts. The `model` section points at any OpenAI-compatible endpoint — Ollama, vLLM, LiteLLM, a cloud provider, whatever you trust.

## Summarization approach

Boswell sends the transcript to a local LLM and asks for structured output: summary, decisions, action items, technical topics, quotes. The default model is IBM Granite 3.2 8B via Ollama, chosen because it runs well on consumer hardware and produces disciplined, factual output.

For higher-stakes meetings, Boswell can cross-reference outputs across multiple models — a pattern called [Meeting of Minds (MoM)](https://zoe-network.github.io/zoe-boswell/mom.html). Send the same transcript to models from different lineages (local via Ollama, cloud via API, or both) and surface where they disagree. Disagreement is signal — it tells you where to focus your attention. The `report` module accepts any OpenAI-compatible endpoint; run it against as many models as you trust and compare the results.

## Project structure

```
boswell/
  __init__.py       # package metadata
  __main__.py       # entry point for python -m boswell
  capture.py        # Whisper + PipeWire transcription
  meeting.py        # combined single-window mode
  advisor.py        # real-time advisory (tails transcript)
  report.py         # post-meeting field report
  context.py        # context builder (calendar, memory, files)
  notify.py         # desktop + terminal notifications
  prompts.py        # system prompt templates
```

## Why not just use Gemini / Otter / Fireflies?

Those tools work. They also mean your meeting audio goes to someone else's server, gets processed by someone else's model, and lives on someone else's infrastructure. You get a summary back. You don't get to choose the model. You don't get to keep the raw transcript private. You don't get to run it on an air-gapped network.

Boswell runs on your laptop. The audio never leaves your machine. The model is whatever you choose to run. The transcript is a text file on your disk. That's it.

## License

Apache 2.0. Zoe is always free — she is code, not a product.
