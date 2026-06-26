# TranscriptX

TranscriptX is a local-first transcript analysis toolkit. It treats transcripts as canonical data and runs deterministic, reproducible analysis pipelines on your machine.

## Why TranscriptX

Most transcript tools are either cloud SaaS (Otter, Fireflies), transcription tools (Whisper, AssemblyAI), or research libraries with limited UX. TranscriptX focuses on analysis. It is designed to:

- analyze transcripts locally
- run modular analysis pipelines
- produce reproducible outputs
- support both personal workflows and academic research

## Supported Entry Points

### Primary: Web app launcher

After install, the `transcriptx` console script starts the Streamlit app (same as `python -m transcriptx.web`).

- Supported flags: `--host`, `--port`
- Env overrides: `TRANSCRIPTX_HOST`, `TRANSCRIPTX_PORT`

### Secondary: Python API

For automation or notebooks, use `transcriptx.app.workflows` with typed requests (for example `AnalysisRequest` + `run_analysis`).

## Architecture (high level)

TranscriptX has two layers:

- **Engine** — Pipeline and modules.
- **GUI** — Streamlit web interface.

For a full architecture overview and extension points, see `docs/ARCHITECTURE.md`.

## Minimal Python workflow

A typical library workflow is:

raw transcript → managed import → analysis

Managed import produces a library-valid transcript under the storage contract; see `docs/runtime/STORAGE.md` and `docs/runtime/transcription.md` for details. A minimal programmatic flow is:

```python
from pathlib import Path

from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis
from transcriptx.io.managed_import_workflow import run_managed_import_workflow

# Import a raw transcript file (WhisperX JSON, SRT, VTT, etc.) into managed storage.
imported = run_managed_import_workflow(
    Path("path/to/raw_transcript.json"),
    overwrite=False,
)

# Then run analysis on the managed canonical JSON path.
result = run_analysis(AnalysisRequest(
    transcript_path=imported.json_path,
    modules=["stats"],
))
print("success:", result.success)
print("status:", result.status)
print("errors:", result.errors)
```

If `result.success` is `False`, inspect `result.errors` for missing optional dependencies or capability-gated modules.

## Quickstart

TranscriptX does not perform audio transcription. Bring your own transcript files from external tools (WhisperX, AssemblyAI, Deepgram, Otter, manual). For how to produce compatible JSON and admit it into managed storage, see `docs/runtime/transcription.md` and `docs/runtime/STORAGE.md`.

**Docker (recommended):** No local Python required.

Copy `.env.example` to `.env` and set **`HOST_RECORDINGS_DIR`** to an absolute path on your machine **outside this repository** (your source-audio folder). Compose mounts it read-only at `/mnt/recordings`.

```bash
docker build -t transcriptx:latest .
docker compose up transcriptx-web
```

Then open http://localhost:8501 in your browser.

**Local install:** Python 3.10+. Core: `pip install transcriptx`. Full optional stack: `pip install transcriptx[full]`. Launcher helper: `./transcriptx.sh`.

For detailed installation, environment variables, NLP setup, and troubleshooting, see [docs/runtime/installation.md](docs/runtime/installation.md).

Configuration precedence (settings UI): Environment → Run/Draft override → Project config → Defaults. See [installation guide](docs/runtime/installation.md) for env vars and gates.

## Canonical sample transcript (development)

For automated tests, integration checks, and local experiments, the repository’s shared minimal fixture is **`tests/fixtures/mini_transcript.json`** (short dialogue, schema v1.0). The Docker first-run script **`scripts/docker-smoke-test.sh`** instead writes a tiny inline example under **`data/transcripts/`** inside your configured data tree; use that flow when validating containers and compose mounts.

## Output artifacts (high-level)

Each analysis run writes structured artifacts under an outputs directory (per-run folders, manifests, and module subdirectories). Full layout and schema details live in:

- `docs/contracts/output-contract-v1.md` — output layout, naming, manifests, and run results.
- `docs/run_outcome_contract.md` — run outcome statuses and precedence rules.
- `docs/dev/pipeline_contracts.md` — core pipeline layering, lifecycle, events, and cleanup invariants.

## Public surfaces

Supported public surfaces are:

- **GUI** (Streamlit web app) — primary interface.
- **Python API** — scripting and automation via typed workflows.
- **Managed import workflow** — the supported way to admit transcripts into managed storage.

See `docs/public_surfaces.md` for the full public-surface contract, including Docker usage, unsupported patterns (e.g. direct CLI analysis subcommands, ad hoc JSON ingestion, and direct filesystem operations on managed storage).

## What TranscriptX does today

- Modular, dependency-aware analysis pipeline
- Speaker and interaction analysis
- Sentiment, emotion, NER, topics, similarity
- Structured, traceable outputs
- Voice prosody dashboards (per-speaker profiles, timelines, comparisons)
- Voice charts core: pause/turn-delivery + rhythm indices (audio-gated)
- Groups: analyze multiple transcripts as a single unit (DB-backed, experimental)

> **Topic modeling note:** `Speaker-Topic Engagement Heatmap` uses shared attribution, not speaker-owned turn counts. Each window contributes one unit of topic engagement total (or the row's existing weight, when present), split evenly across the speakers named in that window.

For **group runs**, which charts appear in the default overview strip versus the full gallery is documented in [docs/groups/group_charts_default_overview.md](docs/groups/group_charts_default_overview.md), including the four modes (**session**, **temporal overlay**, **cross-session speaker**, **pooled single view**) and allowlists (`CROSS_SESSION_SPEAKER_OVERVIEW_ALLOWLIST`, `POOLED_GROUP_OVERVIEW_ALLOWLIST`).

Which modules emit **registry-backed group charts** vs **special-path visuals** (e.g. wordclouds) vs **data-only** or **blob-only** group outputs is summarized in [docs/groups/group_analysis_module_outputs.md](docs/groups/group_analysis_module_outputs.md).

> **TranscriptX runs in file-first mode out of the box.** Groups, corrections, speaker mapping, and search/discovery are all backed by files and sidecars.

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

- [Contract index](docs/CONTRACT_INDEX.md) — where each concept is defined
- [Terminology index](docs/TERMS.md) — canonical vocabulary (links to contracts)
- [Installation & configuration](docs/runtime/installation.md) — NLP setup, gates, core mode, env vars, troubleshooting
- [Transcription guide](docs/runtime/transcription.md) — Canonical schema, how to produce transcript JSON
- [Docker guide](docs/runtime/docker.md) — Volume layout, Apple Silicon, pitfalls
- [Architecture](docs/ARCHITECTURE.md) — Engine, GUI, data flow
- [Developer quickstart](docs/dev/developer_quickstart.md) — Adding modules, pipeline structure
- [Roadmap](docs/ROADMAP.md) — Full roadmap and phases
- [Group charts: default overview vs gallery](docs/groups/group_charts_default_overview.md) — Default strip, four chart modes, gallery-only charts, allowlists
- [Group analysis module outputs](docs/groups/group_analysis_module_outputs.md) — Registry vs special-path vs data-only vs blob-only group modules
