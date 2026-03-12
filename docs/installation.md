# Installation & Configuration

This document covers detailed installation, NLP setup, gates, core mode, environment variables, and troubleshooting. For a quick start, see the [README](../README.md).

## Installation

### Docker (recommended)

No local Python required. Build and run:

```bash
docker build -t transcriptx:latest .
docker compose up transcriptx-web
```

Then open http://localhost:8501. Full details: [docker.md](docker.md).

### Local install

**Python 3.10 or later** required.

**Launcher (fast path):** Creates a virtual environment, installs full dependencies, and starts the web interface:

```bash
./transcriptx.sh
```

With no arguments, starts the web interface at http://localhost:8501. Core-only: `TRANSCRIPTX_CORE=1 ./transcriptx.sh`.

**Manual install:**

- **Core:** `pip install transcriptx` (core only; core_mode on)
- **Full:** `pip install transcriptx[full]` (all modules; core_mode off)
- **Specific extras:** `pip install transcriptx[voice]`, `pip install 'transcriptx[nlp]'`, etc.

**Verify (Python API):**

```python
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis

result = run_analysis(AnalysisRequest(
    transcript_path="tests/fixtures/mini_transcriptx.json",
    modules=["stats"],
))
print("success:", result.success)
```

## NLP: two things, not one

Some features (topic modeling, named-entity recognition, etc.) use NLP — software that understands language. In TranscriptX that comes in **two separate steps**:

1. **The NLP extra** — The program that does language processing. Install via `pip install 'transcriptx[nlp]'`. The launcher's fast path includes this.
2. **The language model** — A separate download: a data file for English (words, grammar, etc.). Run **once** after the NLP extra is installed:

   ```bash
   python -m spacy download en_core_web_md
   ```

If you install the NLP extra but never download the model, analyses that need it (e.g. topic modeling) will fail. Both are required.

## Analysis presets

When you run analysis, you choose a **Preset** (or an explicit module list) that determines which modules run. Use mode `quick` (default) or `full` to control depth.

- **Recommended** — Default set of modules: safe, non-heavy, runnable for the current transcript (skips audio-required modules when audio is missing, heavy modules when deps unavailable). Best for most sessions.
- **All modules** — Every available module (subject to mode and pipeline requirements). Use for full coverage.
- **Light modules only** — Only light-category modules (fast, low-cost). Excludes medium and heavy.
- **Custom** — Pick exactly which modules to run. Only runnable modules are offered.

### Single-speaker behavior

Some modules require multiple named speakers (conversation loops, contagion, interactions, semantic similarity, Q&A, echoes). When a transcript has only one named speaker, these modules are automatically skipped. For group runs, the module list is filtered by the minimum named speaker count across members.

## Gates

Gates are checks that block or skip work to keep results accurate and runs predictable.

- **Speaker identification gate** — Prompts to identify speakers before analysis so per-speaker outputs are meaningful.
- **Audio/default-module gate** — Audio-required modules are included in defaults only when audio is resolvable and required optional extras are available. In core mode, only modules without required_extras are offered. Override by passing an explicit module list.
- **Pipeline requirements gate** — Modules are skipped when transcript capabilities (segments, timestamps, speaker labels, database) do not meet requirements.
- **Downloads gate** — Downloads are opt-in via `TRANSCRIPTX_DISABLE_DOWNLOADS=0`. spaCy model auto-download is allowed by default when not in core mode unless `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1`.
- **Test/CI gates** — Contributor-only smoke/fast gates; see `Makefile` and `tests/README.md`.

## Core mode and optional deps

- **core_mode** — When **on** (default for core installs), only modules without optional extras are available; missing packages are never auto-installed. When **off** (full install or launcher default), all modules are shown and optional imports may trigger `pip install transcriptx[extra]` on first use.
- **Env:** `TRANSCRIPTX_CORE=1` turns core mode on; `TRANSCRIPTX_CORE=0` turns it off.
- Set `TRANSCRIPTX_NO_AUTO_INSTALL=1` to disable automatic pip installs when core mode is off.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `TRANSCRIPTX_HUGGINGFACE_TOKEN` / `HF_TOKEN` | Hugging Face token for diarization and model access. Set one or both; `TRANSCRIPTX_HUGGINGFACE_TOKEN` takes precedence. |
| `TRANSCRIPTX_DISABLE_DOWNLOADS` | `1` (default) — disable model/data downloads. `0` — allow downloads (sentiment, emotion). Does not affect spaCy; use `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD` for that. |
| `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD` | `1` — disable spaCy model auto-download (CI/offline). Unset — allow. When disabled, install manually: `python -m spacy download en_core_web_md`. |
| `TRANSCRIPTX_SPACY_MODEL` | Override default spaCy model (default `en_core_web_md`). |
| `TRANSCRIPTX_CORE` | `1` — enable core mode. `0` — disable. Overrides config file. |
| `TRANSCRIPTX_NO_AUTO_INSTALL` | `1` — disable automatic installation of optional extras (even when core mode is off). |
| `TRANSCRIPTX_HOST` | Host for the web interface (default `127.0.0.1`; use `0.0.0.0` for Docker). |
| `TRANSCRIPTX_PORT` | Port for the web interface (default `8501`). |

**Configuration:** TranscriptX uses env-first configuration with explicit overrides. Unknown/unmapped speakers are excluded from analysis by default; excluded segment counts are reported in run summaries. See [ARCHITECTURE.md](ARCHITECTURE.md) for data layout.

## Web interface (Streamlit)

The Streamlit app reads options from `.streamlit/config.toml` when present.

- **File upload limit** — Audio Prep (and other upload widgets) accept files up to **500 MB per file**. This is set in `.streamlit/config.toml` as `[server] maxUploadSize = 500` (value in megabytes). To change it, edit that file or set the `STREAMLIT_SERVER_MAX_UPLOAD_SIZE` environment variable.

## Troubleshooting

- **"No module named …" after install** — For an editable install from source, install dependencies first: `pip install -r requirements.txt` then `pip install -e .`. If you installed via `pip install transcriptx` or `pip install transcriptx[full]`, dependencies are pulled from pyproject.toml; reinstall with the desired extra if a module fails.
- **spaCy model errors** — The language model is a separate download from the NLP extra. Install the NLP extra first, then run `python -m spacy download en_core_web_md`. If offline and auto-download fails, install manually.
- **Download-related failures** — Downloads are off by default. For features that need models, set `TRANSCRIPTX_DISABLE_DOWNLOADS=0` and (where required) provide a Hugging Face token or policy.
