Type: PRODUCT
Authority: docs/PRODUCT.md

# TranscriptX

**TranscriptX** is a local-first personal transcript analysis workbench for people who want to think with transcripts.

Import and organise transcripts on your machine; explore language, themes, speakers, interactions, emotion, voice and conversational dynamics; use structured analyses and optional local AI to find useful patterns; compare over time; inspect and export machine-readable results — without sending your corpus to a cloud analysis SaaS.

Product definition (authoritative): [docs/PRODUCT.md](docs/PRODUCT.md).

## Get started

TranscriptX does **not** transcribe audio itself. Bring transcript files from external tools (WhisperX, AssemblyAI, Deepgram, Otter, manual, …). See [transcription](docs/runtime/transcription.md) and [storage](docs/runtime/STORAGE.md).

### Docker (no local Python)

Copy `.env.example` to `.env` and set **`HOST_RECORDINGS_DIR`** to an absolute path **outside this repository**.

```bash
docker build -t transcriptx:latest .
docker compose up transcriptx-web
```

Open http://localhost:8501.

### Local install (from git — not PyPI)

Python 3.10–3.12. Core: `pip install -e .`. GUI: `pip install -e ".[web]"`. Analysis extras: `pip install -e ".[full]"` (Streamlit is **not** in `[full]` — use `.[full,web]` or `./transcriptx.sh` for a native GUI). Helper: `./transcriptx.sh` (creates a `.transcriptx` venv; CUDA left available unless `TRANSCRIPTX_FORCE_CPU=1` — see [installation](docs/runtime/installation.md)).

Runtime install markers today are **`core`** and **`full`** only (aspirational `basic`/`llm` profile names are not implemented). Streamlit is the separate **`[web]`** extra.

Details: [installation](docs/runtime/installation.md) · [install verification matrix](docs/runtime/install_verification_matrix.md) · [known limitations](docs/known_limitations.md).

## How you use it

| Surface | Role |
|---------|------|
| **GUI** (`transcriptx`) | Primary — import, analyse, browse, settings |
| **Python API** | Scripting via `transcriptx.app.workflows` |
| **Managed import** | Only supported way to admit transcripts into the library |

```python
from pathlib import Path

from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis
from transcriptx.io.managed_import_workflow import run_managed_import_workflow

imported = run_managed_import_workflow(Path("path/to/raw_transcript.json"), overwrite=False)
result = run_analysis(AnalysisRequest(transcript_path=imported.json_path, modules=["stats"]))
print(result.success, result.status, result.errors)
```

More: [generated CLI / API notes](docs/generated/cli.md) · [public surfaces](docs/public_surfaces.md).

## What it does today

- Modular, dependency-aware analysis pipeline with structured, traceable outputs
- Speaker, interaction, sentiment, emotion, NER, topics, similarity, voice/prosody
- Groups: analyse multiple transcripts together (file-backed); optional local LLM synthesis
- File-first by default — groups, corrections, speaker maps, and discovery use files/sidecars
- **Guided / Full controls** presentation modes and an optional **demo project** for first-run exploration (0.9.6)

## Architecture (brief)

**Engine** (pipeline + modules) and **GUI** (Streamlit). Invariants live in contracts, not this README — see [ARCHITECTURE.md](docs/ARCHITECTURE.md) and [CONTRACT_INDEX.md](docs/CONTRACT_INDEX.md).

## Direction

Stabilisation toward a credible **1.0** (schema epoch through Guided/demo **0.9.6**, automatable harden + public landing **0.9.7**, then unfamiliar-user validation) — not feature-count sprawl. Longer term: personal audio intelligence companion. See [ROADMAP.md](docs/ROADMAP.md) and [pre_release_roadmap_1_0.md](docs/dev/pre_release_roadmap_1_0.md).

## Links

- [Website](website/index.html) (modest public landing; GitHub Pages workflow)
- [User docs index](docs/USER_INDEX.md)
- [Developer docs index](docs/DEV_INDEX.md)
- [Contract index](docs/CONTRACT_INDEX.md)
- [Installation](docs/runtime/installation.md) · [Transcription](docs/runtime/transcription.md) · [Docker](docs/runtime/docker.md)
- [Maintainer Docker smoke](scripts/docker-smoke-test.sh) — compose + `transcriptx --help` only (does **not** write sample transcripts)
- Third-party model notice: [NOTICE](NOTICE)
