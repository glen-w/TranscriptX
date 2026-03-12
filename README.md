# TranscriptX

TranscriptX is a modular transcript analysis toolkit. It treats transcripts as canonical data and runs deterministic, reproducible analysis pipelines locally.

## Why TranscriptX

Most transcript tools are either cloud SaaS (Otter, Fireflies), transcription tools (Whisper, AssemblyAI), or research libraries with little UX. TranscriptX focuses on **analysis**. It is designed to:

- analyze transcripts locally
- run modular analysis pipelines
- produce reproducible outputs
- support both personal workflows and academic research

## Architecture

TranscriptX has two layers:

- **Engine** — Pipeline and modules. DAG-based, dependency-aware execution.
- **GUI** — Streamlit web interface for transcript processing, speaker identification, analysis browsing, batch operations, and settings.

The pipeline is deterministic, DAG-based, and dependency-aware. Scripting and automation use the Python API directly (`app.workflows`, `core.pipeline`).

## Design Principles

TranscriptX is: local-first, modular, reproducible, extensible, and transcript-centric. Modules can be added without modifying the pipeline. Every output traces back to its input, configuration, and the modules that produced it.

## Example

**Input:** A meeting transcript (JSON, e.g. from WhisperX, AssemblyAI, Deepgram, or manual export).

Open the web interface and run analysis from the browser — or via the Python API:

```python
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis

result = run_analysis(AnalysisRequest(
    transcript_path="meeting_transcriptx.json",
    modules=["stats"],
))
```

**Outputs:** speaker statistics, sentiment timelines, named entities, interaction networks, summary artifacts.

## Quickstart

TranscriptX does not perform audio transcription. Bring your own transcript JSON from external tools (WhisperX, AssemblyAI, Deepgram, Otter, manual). See [docs/transcription.md](docs/transcription.md) for the canonical schema and how to produce compatible JSON.

**Docker (recommended):** No local Python required.

```bash
docker build -t transcriptx:latest .
docker compose up transcriptx-web
```

Then open http://localhost:8501 in your browser.

**Local install:** Python 3.10+. Core: `pip install transcriptx`. Full: `pip install transcriptx[full]`. Launcher: `./transcriptx.sh`.

For detailed installation, environment variables, NLP setup, and troubleshooting, see [docs/installation.md](docs/installation.md).

## What TranscriptX Does Today

- Modular, dependency-aware analysis pipeline
- Speaker and interaction analysis
- Sentiment, emotion, NER, topics, similarity
- Structured, traceable outputs
- Voice prosody dashboards (per-speaker profiles, timelines, comparisons)
- Voice charts core: pause/turn-delivery + rhythm indices (audio-gated)
- Groups: analyze multiple transcripts as a single unit (DB-backed, experimental)

> **Database features are experimental and disabled by default.** TranscriptX runs in file-first mode out of the box. Enable database mode with `TRANSCRIPTX_DB_ENABLED=1` — see [docs/installation.md](docs/installation.md) for all DB env vars.

## Product Direction

TranscriptX is evolving toward a **personal audio analysis companion**. Long-term goals include analyzing personal recordings, voice note workflows, conversational analytics, and integration with local AI models. Tools like Plaud, Granola, and Otter address similar spaces, but TranscriptX is **local-first and modular** — your data stays on your machine, and the pipeline is yours to extend.

## Roadmap

**Current stage:** transcript analysis toolkit (beta).

Next phases:

1. Improved UX and stability
2. Richer analysis modules
3. Personal audio analysis workflows
4. Integration with local LLMs (Ollama)
5. Optional remote compute workflows (e.g. Colab)

## Links

- [Installation & configuration](docs/installation.md) — NLP setup, gates, core mode, env vars, troubleshooting
- [Transcription guide](docs/transcription.md) — Canonical schema, how to produce transcript JSON
- [Docker guide](docs/docker.md) — Volume layout, Apple Silicon, pitfalls
- [Architecture](docs/ARCHITECTURE.md) — Engine, GUI, data flow
- [Developer quickstart](docs/developer_quickstart.md) — Adding modules, pipeline structure
- [Roadmap](docs/ROADMAP.md) — Full roadmap and phases
