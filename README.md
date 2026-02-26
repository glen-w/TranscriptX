# TranscriptX

TranscriptX is a place to tinker with transcripts and converse with conversations.

It is an exploratory analysis toolkit for working with conversations when you do not yet know what will matter. Sometimes that means fast, multi-angle inspection. Other times it means slower, longitudinal work across many transcripts over time.

Transcripts are treated as canonical data. Analyses are reproducible, traceable, and configuration-aware.

## Product Philosophy

TranscriptX is a deterministic CLI-first analysis engine.

- **The CLI is the primary interface for:** transcript processing, speaker identification, module selection, preset configuration, and group operations.
- **The Web Viewer is:** read-only; a structured browser for run outputs; designed to eliminate manual folder navigation. It is not a workflow tool and not an editing interface.

The CLI enables reproducibility, scripting, and deterministic runs. Complex multi-step workflows (such as speaker mapping) are more transparent in a terminal-first model. The viewer reads from stable run artifacts and manifests—no mutation, no run creation from the browser.

## Finding the right workflow

### Exploratory — “What’s going on here?”

Run a transcript through multiple analysis modules to surface speaker dynamics, tone, emotion, and structure.

### Longitudinal — “How is this changing over time?”

Run comparable analyses across many transcripts to track trends and evolution.

### Audit/trace  — “Where did this result come from?”

Inspect manifests, configuration snapshots, and module outputs.

These flows describe intent, not enforced modes.

## Inputs & scope

TranscriptX currently treats transcripts as its canonical input. The conceptual focus is on conversations and interactions.

## Quickstart

**Docker Compose (recommended):** No local Python required. From the repo root:

```bash
# Build
docker build -t transcriptx:latest .
# or: docker compose build

# Run everything (CLI in foreground, WhisperX and web viewer in background)
docker compose up
```

Open http://localhost:8501 for the web viewer. **Stop everything:** Ctrl+C in the terminal where you ran `docker compose up`, or run `docker compose down`.

- **Run only the CLI** (e.g. if services are already up): `docker compose run --rm transcriptx`
- **One-off analysis:** `docker compose run --rm transcriptx analyze -t /data/transcripts/foo_transcriptx.json --modules stats --skip-confirm`

Full details (volume layout, Apple Silicon, WhisperX, pitfalls): **[docs/docker.md](docs/docker.md)**.

---

**Alternative: local install**

**Fast path (launcher):** The launcher script creates and uses a virtual environment named `.transcriptx` and installs **full** dependencies (all optional extras) for you. That gives you all modules runnable by default and **core_mode** off:

```bash
./transcriptx.sh
```

With no arguments, this starts the interactive CLI. To open the Web Viewer instead: `./transcriptx.sh web-viewer`. To install only **core** dependencies: `TRANSCRIPTX_CORE=1 ./transcriptx.sh`.

**Manual install:** You need Python 3.10 or later.

- **Core install:** `pip install transcriptx` (core only; **core_mode** on).
- **Full install:** `pip install transcriptx[full]` (all modules; **core_mode** off). You can also install specific extras, e.g. `pip install transcriptx[voice]`, `pip install 'transcriptx[nlp]'`, and use **transcriptx deps install** to add more later (see below).

#### NLP: two things, not one

Some features (topic modeling, named-entity recognition, and similar) use “NLP” — software that understands language. In    TranscriptX that comes in **two separate steps**:

1. **The NLP extra** — This is the program that does the language processing. You get it by choosing the “nlp” (or “full”) install option, e.g. `pip install 'transcriptx[nlp]'`. The launcher’s fast path already includes this.
2. **The language model** — This is a separate download: a data file the program uses for English (words, grammar, etc.). It is **not** installed when you install TranscriptX or the NLP extra. You need to run this **once** after the NLP extra is installed:
   ```bash
   python -m spacy download en_core_web_md
   ```

If you only install the NLP extra but never download the model, analyses that need it (e.g. topic modeling) will fail and ask you to install the model. So: **install the NLP extra** = you have the tool; **download the model** = you give it the language data. Both are required for those analyses.

**Verify install:** Docker: `docker compose run --rm transcriptx --help` and/or a minimal analysis (e.g. with a fixture: `-v "$(pwd)/tests/fixtures:/fixtures:ro"` and `-t /fixtures/mini_transcriptx.json`). Local install: run `transcriptx --help`, then:

```bash
transcriptx analyze -t tests/fixtures/mini_transcriptx.json --modules stats --skip-confirm
```

For all commands and options, see the [CLI reference](docs/CLI.md).

**Web Viewer:** With the environment activated:

```bash
transcriptx web-viewer
```

### Analysis presets (CLI)

When you run analysis from the CLI, you choose a **Preset** (or an explicit module list) that determines which analysis modules run. Use `--mode quick` (default) or `--mode full` to control analysis depth. The Web Viewer then lets you browse the outputs of those runs.

- **Recommended** — Runs the default set of modules: safe, non-heavy, and runnable for the current transcript (e.g. skips audio-required modules when audio is missing, and heavy/optional-deps modules when not available). Best for most sessions.
- **All modules** — Runs every available analysis module (subject to mode and pipeline requirements). Use when you want full coverage.
- **Light modules only** — Runs only modules in the *light* category (fast, low-cost processing). Excludes *medium* and *heavy* modules. Use for quick passes or when you want to avoid slower/heavier analyses.
- **Custom** — Lets you pick exactly which modules to run. Only modules that are runnable for the current session (e.g. audio/deps satisfied) are offered.

### Single-speaker behavior

Some analysis modules require multiple named speakers (e.g. conversation loops, contagion, interactions, semantic similarity, Q&A, echoes). When a transcript has only one named speaker, these modules are automatically skipped and are not shown in the selection menu. For group runs, the module list is filtered using the minimum named speaker count across member transcripts to avoid offering modules that would be skipped for part of the group.

## Groups (first-class, DB-backed)

Groups are durable user objects that let you analyze multiple transcripts as a single unit.

Create a group (paths or transcript_file UUIDs):

```
transcriptx group create --name "Workshop 2026-02" --type merged_event \
  --transcripts /path/a.json,/path/b.json
```

List groups (optional type filter):

```
transcriptx group list --type merged_event
```

Show a group by identifier (UUID, key, or name):

```
transcriptx group show --identifier <uuid-or-key-or-name>
```

Run analysis for a group:

```
transcriptx group run --identifier <uuid-or-key-or-name> --modules all
```

Delete a group:

```
transcriptx group delete --identifier <uuid-or-key-or-name> --force
```

Group runs write outputs under `outputs/groups/<group_uuid>/<run_id>/` and include
`group_manifest.json` with the exact membership and key used at run time.

### Group aggregations (v2 rows)

Group runs write standardized row outputs under:
`outputs/groups/<group_uuid>/<run_id>/<agg_id>/`.

Each row-based aggregation writes:
- `session_rows.json` / `session_rows.csv` (per transcript)
- `speaker_rows.json` / `speaker_rows.csv` (per canonical speaker)
- optional `metrics_spec.json`
- optional content rows (e.g. `highlight_rows.json` / `moment_rows.json`)
- `aggregation.json` bundle (rows + spec)

Warnings are recorded once at the end of a group run in
`aggregation_warnings.json` with structured codes (e.g. `MISSING_DEP`,
`PAYLOAD_SHAPE_UNSUPPORTED`, `MISSING_ARTIFACT`, `SCHEMA_VALIDATION_FAILED`).

## What TranscriptX does today

- Modular, dependency-aware analysis pipeline
- Speaker and interaction analysis
- Sentiment, emotion, NER, topics, similarity
- Structured, traceable outputs
- Voice prosody dashboards (per-speaker profiles, timelines, comparisons)
- Voice charts core: pause/turn-delivery + rhythm indices (audio-gated)
- Voice contours (opt-in; slower, pitch tracking)
- Optional audio transcription via WhisperX

## Outputs & guarantees

Each run produces a self-contained directory with configuration snapshots, a manifest, and module outputs. Outputs are deterministic and traceable. Voice artifacts live under a versioned namespace (e.g. `voice/v1/`).
affect_tension outputs include JSON/CSV plus charts for derived indices, per-segment dynamics, and mismatch heatmaps (speaker comparisons and global views).

## Configuration & conventions

Configuration is env-first with explicit overrides. **Unknown/unmapped speakers are excluded from analysis** by default; the number of excluded segments is reported in run summaries and in stats provenance where applicable. Audio-required modules are gated: defaults include them only when audio is resolvable and (when not in core mode) required optional deps are available or auto-installed. Optional extras (voice, emotion, nlp, etc.) can be installed via **transcriptx deps install** or **pip install transcriptx[extra]**; in non–core mode, missing extras may be auto-installed on first use.
Downloads are disabled by default; opt in by setting `TRANSCRIPTX_DISABLE_DOWNLOADS=0` and (for transcription models) providing a Hugging Face token or setting the download policy explicitly.

### Gates

Gates are checks that prompt, block, or skip work to keep results accurate and runs predictable.

- Speaker identification gate (CLI): prompts to identify speakers before analysis so per-speaker outputs are meaningful. Can be bypassed via workflow `skip_speaker_gate` or forced non-interactive mode in `check_speaker_gate()`. See `src/transcriptx/cli/speaker_utils.py`.
- Audio/default-module gate: audio-required modules are included in defaults only when audio is resolvable and (when not in core mode) required optional extras are available or auto-installed. In core mode, only modules without required_extras are offered. Override by passing an explicit module list. See `src/transcriptx/core/pipeline/module_registry.py` and `src/transcriptx/core/utils/audio_availability.py`.
- Pipeline requirements gate: modules are skipped when transcript capabilities (segments, timestamps, speaker labels, database) do not meet requirements. See `src/transcriptx/core/pipeline/requirements_resolver.py`.
- Downloads gate: downloads are opt-in via `TRANSCRIPTX_DISABLE_DOWNLOADS=0` (sentiment, emotion). spaCy model auto-download is allowed by default when not in core mode unless `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1`. See `src/transcriptx/core/utils/nlp_runtime.py`.
- Test/CI gates: contributor-only smoke/fast gates keep CI deterministic; see `Makefile` and `tests/README.md`.

### Core mode and optional deps

- **core_mode** — When **on** (default for core installs), only modules that do not require optional extras are available, and missing optional packages are never auto-installed. When **off** (e.g. after a full install or launcher default), all modules are shown (missing extras are tagged as “installs on first run”) and optional imports may trigger **pip install transcriptx[extra]** on first use.
- **CLI flags:** `--core` forces core mode on; `--no-core` forces it off. Resolution order: CLI > env > config file > install profile.
- **Env:** `TRANSCRIPTX_CORE=1` turns core mode on; `TRANSCRIPTX_CORE=0` turns it off.
- **Deps commands:** Use **transcriptx deps status** to see which extras are available/missing and the current core_mode. Use **transcriptx deps install --full** to install all extras, or **transcriptx deps install voice emotion nlp** (etc.) to install selected extras. In non–core mode, set **TRANSCRIPTX_NO_AUTO_INSTALL=1** to disable automatic pip installs.

### Environment variables

- **Hugging Face token** — For diarization and some model access you can set either `TRANSCRIPTX_HUGGINGFACE_TOKEN` or `HF_TOKEN`; set **one** (or both). `TRANSCRIPTX_HUGGINGFACE_TOKEN` takes precedence. We support both so that: (1) if you already use `HF_TOKEN` elsewhere (e.g. Hugging Face CLI, Docker images like WhisperX), you don’t need a second variable; (2) if you want an app-specific name or a different token for TranscriptX, use `TRANSCRIPTX_HUGGINGFACE_TOKEN`. For Docker, you can use a file-based secret; see [docs/docker.md](docs/docker.md).
- `TRANSCRIPTX_DISABLE_DOWNLOADS` — Set to `1` (default) to disable model/data downloads; set to `0` to allow downloads (e.g. for sentiment, emotion). Does not affect spaCy model auto-download; use `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD` for that.
- `TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD` — Set to `1` (or true/yes/on) to disable spaCy model auto-download (for CI/offline). Default is unset (allow). When disabled, install manually: `python -m spacy download en_core_web_md`.
- `TRANSCRIPTX_SPACY_MODEL` — Override default spaCy model (default `en_core_web_md`). Used by runtime and launcher.
- `TRANSCRIPTX_CORE` — Set to `1` to enable core mode (only core modules, no auto-install); `0` to disable. Overrides config file; CLI `--core`/`--no-core` override env.
- `TRANSCRIPTX_NO_AUTO_INSTALL` — Set to `1` to disable automatic installation of optional extras (even when core mode is off).
- `TRANSCRIPTX_USE_EMOJIS` — Set to `0` to disable emojis in CLI output (e.g. for CI or plain terminals).

### Troubleshooting

- **"No module named …" after install** — Ensure you ran `pip install -r requirements.txt` before `pip install -e .`. The package does not bundle runtime dependencies.
- **spaCy model errors** — The language model is a separate download from the NLP extra. See **NLP: two things, not one** in Quickstart: install the NLP extra first, then run `python -m spacy download en_core_web_md` (and optionally `en_core_web_sm`). If offline and auto-download fails, install manually: `python -m spacy download en_core_web_md`.
- **Download-related failures** — Downloads are off by default. For features that need models, set `TRANSCRIPTX_DISABLE_DOWNLOADS=0` and (where required) provide a Hugging Face token or policy.

## Power users & developers

TranscriptX is built around a DAG-based pipeline, a shared context, and strict artifact contracts. See [developer_quickstart.md](docs/developer_quickstart.md) for extension guidance.

## Scope and non-goals (v0.42)

v0.42 does **not** include: a plugin system, a hosted service, or real-time processing. The CLI and Web Viewer are the supported interfaces; database and cross-session commands are CLI-only. See the [roadmap](docs/ROADMAP.md) for what is planned later.

## What’s next

See the [roadmap](docs/ROADMAP.md) for near-term direction and deferred features. Database and cross-session speaker commands (`transcriptx database`, `transcriptx cross-session`) are available as **CLI-only**; speaker-over-time visualization and richer DB-backed analytics in the Web Viewer are planned for a later release.
