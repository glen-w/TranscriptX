# Installation details

Advanced / developer reference. For the normal Docker or `./transcriptx.sh` path, see [Installation](installation.md).

Operational guide only. Storage and metadata: [STORAGE.md](STORAGE.md). Run statuses: [run_outcome_contract.md](../run_outcome_contract.md). Output layout: [output-contract-v1.md](../contracts/output-contract-v1.md). Supported interfaces: [public_surfaces.md](../public_surfaces.md).

## Manual install (from this repository — not PyPI)

Authoritative verification cells: [install_verification_matrix.md](install_verification_matrix.md).

- **Core (editable):** `pip install -e .`
- **GUI only:** `pip install -e ".[web]"` (Streamlit; not part of `[full]`)
- **Full analysis extras:** `pip install -e ".[full]"` (all optional analysis modules; core_mode off; may fail on some hosts; **does not** install Streamlit)
- **Native GUI ≈ Docker:** `pip install -e ".[full,web]"` or use `./transcriptx.sh` / `requirements.txt`
- **Specific extras:** `pip install -e ".[voice]"`, `pip install -e '.[nlp]'`, `pip install -e ".[keyphrases]"` (optional YAKE / KeyBERT for the `keyphrases` module; noun-chunks path works without the extra), `pip install -e ".[visualization]"` (charts helpers + Overview export EPUB via `ebooklib`), `pip install -e ".[speaker_match]"`, etc.

### Install profiles

Runtime markers today are **`core` | `full` only**. Streamlit lives in the **`[web]`** extra and in Docker/`requirements.txt`/`transcriptx.sh` — not in `[full]`. Aspirational names such as `basic` / `llm` as separate install profiles are **not** implemented. Docker images follow the fuller dependency set via `requirements.txt` / image build — that is **not** the same path as `pip install -e ".[full]"`. Treat Docker, `./transcriptx.sh`, and editable extras as related but non-equivalent install stories. See [install_profiles_matrix.md](../dev/install_profiles_matrix.md).

**BERTopic:** The module worked in base for a while. It was moved to **`[bertopic]`** (also in `[full]` / Docker) so **core** wheel / clean-env installs are not blocked by `umap-learn`→`numba`→`llvmlite` source builds on some hosts. Missing packages do not fail the build; runs degrade with `missing_extra:bertopic`. Full story: [bertopic_optional_module.md](../dev/bertopic_optional_module.md).

**Dedicated environment:** TranscriptX does not use Prefect, Dagster, or other workflow engines. For a clean environment with only project dependencies:

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"     # core + lint/test tools (pytest); add [voice], [nlp], etc. as needed
```

**Launcher GPU note:** By default `transcriptx.sh` leaves CUDA visible when present. Opt into CPU-only with `TRANSCRIPTX_FORCE_CPU=1 ./transcriptx.sh` (clears `CUDA_VISIBLE_DEVICES` for that shell). Native Mac (Apple Silicon) MPS is **supported-with-caveats** — see [known limitations](../known_limitations.md).

### Verify (Python API)

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

## Gates

Gates are checks that block or skip work to keep results accurate and runs predictable.

- **Speaker identification gate** — Prompts to identify speakers before analysis so per-speaker outputs are meaningful. Analysis also skips modules until speakers are named unless you ungate via `analysis.allow_unnamed_speakers` / the per-run checkbox. See [Settings](settings.md#analysis-presets).
- **Audio/default-module gate** — Audio-required modules are included in defaults only when audio is resolvable and required optional extras are available. Core mode does not hide modules. Override by passing an explicit module list.
- **Pipeline requirements gate** — Modules are skipped when transcript capabilities (segments, timestamps, speaker labels, etc.) do not meet requirements.
- **Downloads gate** — Downloads are enabled by default. Set `TRANSCRIPTX_DISABLE_DOWNLOADS=1` to force offline/no-download behavior. spaCy model auto-download is allowed by default when not in core mode unless `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1`.
- **Test/CI gates** — Contributor-only smoke/fast gates; see `Makefile` and `tests/README.md`.

## Core mode and optional deps

- **core_mode** — Core mode does not hide modules. It controls install/download behavior (for example, preventing automatic dependency installs) while module availability remains the same.
- **Env:** `TRANSCRIPTX_CORE=1` turns core mode on; `TRANSCRIPTX_CORE=0` turns it off.
- Set `TRANSCRIPTX_NO_AUTO_INSTALL=1` to disable automatic pip installs when core mode is off.

## File-native storage (summary)

TranscriptX runs in file-first mode by default, with groups, corrections, and other artifacts backed by files. The full storage and metadata contract is [STORAGE.md](STORAGE.md).

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
| `INBOX_WATCH_ADMIT` | Host USB/inbox watcher: `1` admits `originals/` into the managed library after convert/STT. Default off. See [host STT automation](host-stt.md#host-inbox-watcher-inbox-watch). |
| `INBOX_WATCH_ADMIT_PYTHON` | Python interpreter for that admit step (must `import transcriptx`). |

**Models:** defaults, higher-accuracy presets, and per-module guidance — [models.md](models.md).

**Configuration:** TranscriptX merges defaults, project/draft/run overrides, and env (`TRANSCRIPTX_*`; env wins). Unknown/unmapped speakers are excluded from analysis by default; excluded segment counts are reported in run summaries. See [STORAGE.md](STORAGE.md) for storage layout and [settings.md](settings.md) for Settings scopes, Common vs Advanced knobs, and how **install profiles** differ from **module/workflow profiles** on the Profiles page.

## Web interface (Streamlit)

**Console entry point:** After install, `transcriptx` runs the same code as `python -m transcriptx.web`. Flags: `--host`, `--port` (defaults `127.0.0.1` and `8501`; also read from `TRANSCRIPTX_HOST` / `TRANSCRIPTX_PORT`). This does not accept analysis subcommands — use the browser UI or the Python API (see [generated/cli.md](../generated/cli.md)).

The Streamlit app reads options from `.streamlit/config.toml` when present.

- **File upload limit** — Upload widgets accept files up to **500 MB per file**. This is set in `.streamlit/config.toml` as `[server] maxUploadSize = 500` (value in megabytes). To change it, edit that file or set the `STREAMLIT_SERVER_MAX_UPLOAD_SIZE` environment variable.
