Type: GUIDE
Authority: runtime/STORAGE.md

# Installation & Configuration

Operational guide only (installation, environment, runtime behavior). For authoritative storage and metadata structure, see `STORAGE.md`. For behavior and invariants, see CONTRACT documents.

This document covers detailed installation, NLP setup, gates, core mode, environment variables, and troubleshooting. It is **not** a storage, run-outcome, or support-policy contract; for those rules, see:

- `docs/runtime/STORAGE.md` — storage and metadata contract.
- `docs/run_outcome_contract.md` — run truth and statuses.
- `docs/contracts/output-contract-v1.md` — output layout and manifests.
- `docs/public_surfaces.md` — supported interfaces and unsupported patterns.

For a quick start, see the [README](../README.md).

## Installation

### Docker (recommended)

No local Python required. Build and run:

```bash
docker build -t transcriptx:latest .
docker compose up transcriptx-web
```

Then open http://localhost:8501. Full details: [docker.md](docker.md).

### Local install

**Python 3.10–3.12** required (`requires-python = ">=3.10,<3.13"`).

**Launcher (fast path):** Creates a `.transcriptx` virtual environment, installs dependencies, and starts the web interface:

```bash
./transcriptx.sh
```

With no arguments, starts the web interface at http://localhost:8501. Core-only: `TRANSCRIPTX_CORE=1 ./transcriptx.sh`.

> **GPU note:** By default `transcriptx.sh` leaves CUDA visible when present. Opt into CPU-only with `TRANSCRIPTX_FORCE_CPU=1 ./transcriptx.sh` (clears `CUDA_VISIBLE_DEVICES` for that shell).

> **Native Mac (Apple Silicon) MPS:** Status is **supported-with-caveats**, not universally validated. Docker **CPU** is the recommended predictable path (Docker on Mac cannot use host GPU/MPS). Native MPS may work for some torch workloads on a given host, but optional models are **not** guaranteed to initialise or execute on MPS. If MPS initialisation or model execution fails, re-run with `TRANSCRIPTX_FORCE_CPU=1` so the fallback is actionable — do not assume every optional model supports MPS reliably. See [known limitations](../known_limitations.md).

**Manual install (from this repository — not PyPI):**

The package is **not published on PyPI**. Do not use bare `pip install transcriptx` from PyPI. Authoritative cells: [install_verification_matrix.md](install_verification_matrix.md).

- **Core (editable):** `pip install -e .`
- **GUI only:** `pip install -e ".[web]"` (Streamlit; not part of `[full]`)
- **Full analysis extras:** `pip install -e ".[full]"` (all optional analysis modules; core_mode off; may fail on some hosts; **does not** install Streamlit)
- **Native GUI ≈ Docker:** `pip install -e ".[full,web]"` or use `./transcriptx.sh` / `requirements.txt`
- **Specific extras:** `pip install -e ".[voice]"`, `pip install -e '.[nlp]'`, `pip install -e ".[keyphrases]"` (optional YAKE / KeyBERT for the `keyphrases` module; noun-chunks path works without the extra), `pip install -e ".[speaker_match]"`, etc.

> **Install profiles (honesty):** Runtime markers today are **`core` | `full` only**. Streamlit lives in the **`[web]`** extra and in Docker/`requirements.txt`/`transcriptx.sh` — not in `[full]`. Aspirational names such as `basic` / `llm` as separate install profiles are **not** implemented. Docker images follow the fuller dependency set via `requirements.txt` / image build — that is **not** the same path as `pip install -e ".[full]"`. Treat Docker, `./transcriptx.sh`, and editable extras as related but non-equivalent install stories. See [install_profiles_matrix.md](../dev/install_profiles_matrix.md).
>
> **BERTopic:** The module worked in base for a while. It was moved to **`[bertopic]`** (also in `[full]` / Docker) so **core** wheel / clean-env installs are not blocked by `umap-learn`→`numba`→`llvmlite` source builds on some hosts. Missing packages do not fail the build; runs degrade with `missing_extra:bertopic`. Full story: [bertopic_optional_module.md](../dev/bertopic_optional_module.md).

**Dedicated environment (recommended):** TranscriptX does not use Prefect, Dagster, or other workflow engines. For a clean environment with only project dependencies, use a fresh virtualenv and install from the repo:

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"     # core + lint/test tools (pytest); add [voice], [nlp], etc. as needed
```

**Verify (Python API):**

```python
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis
from transcriptx.io.managed_import_workflow import run_managed_import_workflow

imported = run_managed_import_workflow(
    "path/to/raw_transcript.json",
    overwrite=False,
)

result = run_analysis(AnalysisRequest(
    transcript_path=imported.json_path,
    modules=["stats"],
))
print("success:", result.success)
print("errors:", result.errors)
```

## NLP: two things, not one

Some features (topic modeling, named-entity recognition, etc.) use NLP — software that understands language. In TranscriptX that comes in **two separate steps**:

1. **The NLP extra** — The program that does language processing. Install via `pip install -e '.[nlp]'`. The launcher's fast path includes this.
2. **The language model** — A separate download: a data file for English (words, grammar, etc.). Run **once** after the NLP extra is installed:

   ```bash
   python -m spacy download en_core_web_md
   ```

If you install the NLP extra but never download the model, analyses that need it (e.g. topic modeling) will fail. Both are required.

## Analysis presets

When you run analysis, choose a **Preset** that determines which modules run:

- **Quick** — no LLM modules and no heavy modules (fast local path). Modules that hard-depend on excluded heavy/LLM modules are omitted so the DAG cannot pull them back in.
- **Balanced** — recommended default: non-heavy modules plus a limited heavy allowlist (`semantic_similarity`, `fine_grained_emotion`) and **global transcript LLM summary only** (`llm_summary`).
- **Thorough** — all suitable modules for the target (including LLM and heavy).
- **Custom** — pick exactly which modules to run for this launch.

Edit Quick / Balanced / Thorough policies (and optional full module overrides) under **Settings → Analysis**. Mode `quick` vs `full` still controls depth knobs (semantic/NER limits) for the chosen preset.

### Single-speaker behavior

Some modules require multiple named speakers (conversation loops, contagion, interactions, semantic similarity, Q&A, echoes). When a transcript has only one named speaker, these modules are automatically skipped. For group runs, the module list is filtered by the minimum named speaker count across members.

## Gates

Gates are checks that block or skip work to keep results accurate and runs predictable.

- **Speaker identification gate** — Prompts to identify speakers before analysis so per-speaker outputs are meaningful.
- **Audio/default-module gate** — Audio-required modules are included in defaults only when audio is resolvable and required optional extras are available. Core mode does not hide modules. Override by passing an explicit module list.
- **Pipeline requirements gate** — Modules are skipped when transcript capabilities (segments, timestamps, speaker labels, etc.) do not meet requirements.
- **Downloads gate** — Downloads are enabled by default. Set `TRANSCRIPTX_DISABLE_DOWNLOADS=1` to force offline/no-download behavior. spaCy model auto-download is allowed by default when not in core mode unless `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1`.
- **Test/CI gates** — Contributor-only smoke/fast gates; see `Makefile` and `tests/README.md`.

## Core mode and optional deps

- **core_mode** — Core mode does not hide modules. It controls install/download behavior (for example, preventing automatic dependency installs) while module availability remains the same.
- **Env:** `TRANSCRIPTX_CORE=1` turns core mode on; `TRANSCRIPTX_CORE=0` turns it off.
- Set `TRANSCRIPTX_NO_AUTO_INSTALL=1` to disable automatic pip installs when core mode is off.

## File-native storage (summary)

TranscriptX runs in file-first mode by default, with groups, corrections, and other artifacts backed by files. The full storage and metadata contract (including groups and corrections) is defined in `docs/runtime/STORAGE.md`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `HF_TOKEN` | Hugging Face token for diarization and gated models. Set in `whisperx.env` (see [WhisperX recipe](../recipes/whisperx/README.md)); passed to the whispermlx subprocess, not stored in TranscriptX config. |
| `TRANSCRIPTX_DISABLE_DOWNLOADS` | Unset/`0` (default) — allow model/data downloads. `1` — disable downloads (sentiment, emotion). Does not affect spaCy; use `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD` for that. |
| `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD` | `1` — disable spaCy model auto-download (CI/offline). Unset — allow. When disabled, install manually: `python -m spacy download en_core_web_md`. |
| `TRANSCRIPTX_SPACY_MODEL` | Override default spaCy model (default `en_core_web_md`). |
| `TRANSCRIPTX_CORE` | `1` — enable core mode. `0` — disable. Overrides config file. |
| `TRANSCRIPTX_NO_AUTO_INSTALL` | `1` — disable automatic installation of optional extras (even when core mode is off). |
| `TRANSCRIPTX_HOST` | Host for the web interface (default `127.0.0.1`; use `0.0.0.0` for Docker). |
| `TRANSCRIPTX_PORT` | Port for the web interface (default `8501`). |

**Models:** defaults, higher-accuracy presets, and per-module guidance — [models.md](models.md).

**Configuration:** TranscriptX uses env-first configuration with explicit overrides. Unknown/unmapped speakers are excluded from analysis by default; excluded segment counts are reported in run summaries. See [STORAGE.md](STORAGE.md) for storage layout.

## Web interface (Streamlit)

**Console entry point:** After install, `transcriptx` runs the same code as `python -m transcriptx.web`. Flags: `--host`, `--port` (defaults `127.0.0.1` and `8501`; also read from `TRANSCRIPTX_HOST` / `TRANSCRIPTX_PORT`). This does not accept analysis subcommands — use the browser UI or the Python API (see [generated/cli.md](generated/cli.md)).

The Streamlit app reads options from `.streamlit/config.toml` when present.

- **File upload limit** — Upload widgets accept files up to **500 MB per file**. This is set in `.streamlit/config.toml` as `[server] maxUploadSize = 500` (value in megabytes). To change it, edit that file or set the `STREAMLIT_SERVER_MAX_UPLOAD_SIZE` environment variable.

## Troubleshooting

- **"No module named …" after install** — For an editable install from source, install dependencies first: `pip install -r requirements.txt` then `pip install -e .`. If you installed via `pip install -e .` or `pip install -e ".[full]"`, dependencies are pulled from pyproject.toml; reinstall with the desired extra if a module fails.
- **spaCy model errors** — The language model is a separate download from the NLP extra. Install the NLP extra first, then run `python -m spacy download en_core_web_md`. If offline and auto-download fails, install manually.
- **Download-related failures** — If your environment blocks network access, set `TRANSCRIPTX_DISABLE_DOWNLOADS=1` and pre-populate/mount required caches (and provide required Hugging Face token/policy where applicable).
