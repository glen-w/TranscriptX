# TranscriptX

TranscriptX is a place to think with transcripts.

It is an exploratory analysis toolkit for working with conversations when you do not yet know what will matter. Sometimes that means fast, visual sense-making (run a meeting, workshop, interview, or chat through a wide range of modules to surface patterns). Other times it means slower, longitudinal work: following speakers, language, tone, or themes across many transcripts over time.

Transcripts are treated as canonical data, analyses run through a reproducible pipeline, and outputs are indexed and traceable. The infrastructure exists so you can experiment freely without silent drift or unclear provenance.

Version: **0.1.0** · Python **3.10+**

## Quick orientation (30-60s)

TranscriptX answers these questions quickly:

- What it is: a modular transcript analysis pipeline with a CLI and a local WebUI.
- What it does today: analyze transcripts, profile speakers, generate structured outputs, and optionally transcribe audio with WhisperX.
- How to run it: `./transcriptx.sh` or `transcriptx` for CLI, `transcriptx web-viewer` for WebUI.
- Where outputs go: `data/outputs/` by default, with a consistent run structure.
- How to extend it: add an analysis module and register it in the module registry.

## Table of contents

- Quickstart
- Interfaces (CLI, WebUI, Docker transcription)
- Capabilities and modules
- Outputs and contracts
- Configuration
- Unknown speaker rule
- Extending TranscriptX
- Troubleshooting

## Quickstart

### Fast path (recommended)

```bash
./transcriptx.sh
```

This launcher creates/activates `.transcriptx/`, installs dependencies, and starts the interactive CLI.

### Manual install (clean venv)

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip install -e .
```

### WebUI (Streamlit)

```bash
transcriptx web-viewer
# or
streamlit run src/transcriptx/web/app.py
```

Default URL: `http://127.0.0.1:8501`

## Interfaces (what exists today)

### CLI (Typer)

The CLI supports both interactive and non-interactive workflows.

Common commands:

- `transcriptx` (interactive)
- `transcriptx --help`
- `transcriptx analyze <transcript.json>`
- `transcriptx transcribe <audio>`
- `transcriptx identify-speakers`
- `transcriptx analysis run ...`
- `transcriptx database ...`
- `transcriptx audit` / `transcriptx doctor`

### WebUI (Streamlit)

The Streamlit UI reads from `data/outputs/` and provides:

- Overview, explorer, charts, data, insights, statistics, groups, search, configuration
- Session browsing and speaker profiles

### Audio transcription (WhisperX via Docker)

Start WhisperX:

```bash
docker-compose -f docker-compose.whisperx.yml --profile whisperx up -d whisperx
```

Then transcribe:

```bash
transcriptx transcribe path/to/audio.mp3
```

Token for diarization (if required by models):

```bash
export TRANSCRIPTX_HUGGINGFACE_TOKEN=...
# or
export HF_TOKEN=...
```

Local WhisperX env file (recommended for Docker):

```bash
cp whisperx.env.example whisperx.env
# paste your HF token into whisperx.env
```

Do not commit `whisperx.env` (it is gitignored).
Optional safety check before pushing: `scripts/secrets_check.sh`.

## Capabilities (what exists today)

### Core analysis capabilities

- Modular analysis pipeline (DAG-based dependencies)
- NLP analysis: sentiment, emotion, NER, topic modeling, semantic similarity
- Speaker interaction analysis: turns, interruptions, conversation loops
- Statistical summaries and reports
- Visual outputs: charts, word clouds, maps

### Storage and provenance

- SQLite-backed database (optional but supported)
- Run manifests with config snapshots and artifact tracking

### Output tools

- Transcript formatting and export
- Artifact validation (`transcriptx artifacts validate`)
- Diagnostic tools (`transcriptx doctor`, `transcriptx audit`)

## Analysis modules (what exists + what it outputs)

Modules are grouped by computational intensity; each produces JSON/CSV/visual outputs inside the run directory:

Light:
- `stats`, `wordclouds`, `tics`, `transcript_output`, `conversation_loops`

Medium:
- `sentiment`, `emotion`, `ner`, `acts`, `interactions`, `understandability`, `temporal_dynamics`, `qa_analysis`

Heavy:
- `topic_modeling`, `semantic_similarity`, `semantic_similarity_advanced`, `entity_sentiment`, `contagion`

Optional:
- `convokit` (requires `convokit` dependency; coordination/accommodation metrics)

## Outputs and contracts (stable)

### Root directories

- `data/recordings/` — input audio files
- `data/transcripts/` — transcript JSON outputs (including diarized transcripts)
- `data/outputs/` — analysis run outputs

### Run directory layout

Each analysis run writes a run folder under `data/outputs/` and includes:

- `.transcriptx/run_config_effective.json` — effective config snapshot
- `.transcriptx/run_config_override.json` (if overrides were used)
- `manifest.json` — artifact listing
- module folders such as `sentiment/`, `stats/`, `transcript_output/`, etc.

Override output root:

- CLI flag: `--output-dir /path/to/outputs`
- Env var: `TRANSCRIPTX_OUTPUT_DIR=/path/to/outputs`

## Configuration (env-first)

Common environment variables:

- `TRANSCRIPTX_HUGGINGFACE_TOKEN` or `HF_TOKEN` (diarization/model access)
- `TRANSCRIPTX_OUTPUT_DIR` (output root)
- `TRANSCRIPTX_LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR)

Config files can also be passed via `--config /path/to/config.json`.

## Unknown speaker rule

Segments may contain `speaker: "UNKNOWN_SPEAKER"` when a speaker is not identified.

By default, **unidentified speakers are excluded from most per-speaker analyses** (e.g., word clouds, sentiment, emotion). This avoids misleading per-speaker outputs. Exceptions that remain inclusive:

- Transcript exports / CSV exports
- NER outputs

## Extending TranscriptX (without reading the whole codebase)

High-level steps:

1. Create a new analysis module class (under `src/transcriptx/core/analysis/`).
2. Implement `run_from_context()` and output artifacts via the output service.
3. Register the module in the module registry.
4. Add a minimal test in `tests/analysis/`.

No plugin system is required for v0.1; this is a lightweight, internal extension pattern.

## Troubleshooting

### ffmpeg / ffprobe missing

Install ffmpeg to enable audio metadata and conversions:

```bash
brew install ffmpeg
# or
sudo apt-get update && sudo apt-get install -y ffmpeg
```

### Docker socket security

The UI+WhisperX compose example mounts `/var/run/docker.sock` into the UI container. This is intended for local development only and is not recommended on shared or multi-tenant hosts.

## Project layout (high level)

```
transcriptx/
├── transcriptx.sh           # Main launcher (venv + CLI)
├── requirements.txt         # Core + ML dependencies
├── requirements-dev.txt     # Dev/test dependencies
├── src/transcriptx/          # Core package
├── scripts/                 # Utility scripts
├── data/                    # Inputs and outputs (not committed)
└── .transcriptx/            # Local venv created by transcriptx.sh
```

## License

MIT (see `LICENSE`).
