# TranscriptX

TranscriptX is a place to think with transcripts and converse with conversations.

It is an exploratory analysis toolkit for working with conversations when you do not yet know what will matter. Sometimes that means fast, multi-angle inspection. Other times it means slower, longitudinal work across many transcripts over time.

Transcripts are treated as canonical data. Analyses are reproducible, traceable, and configuration-aware.

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

Fast path:

./transcriptx.sh

Manual install:

python3.10 -m venv .venv  
source .venv/bin/activate  
pip install -e .

WebUI:

transcriptx web-viewer

### Run Analysis presets (Web UI)

When you run analysis from the web UI, you choose a **Preset** that determines which analysis modules run:

- **Recommended** — Runs the default set of modules: safe, non-heavy, and runnable for the current transcript (e.g. skips audio-required modules when audio is missing, and heavy/optional-deps modules when not available). Best for most sessions.
- **All modules** — Runs every available analysis module (subject to mode and pipeline requirements). Use when you want full coverage.
- **Light modules only** — Runs only modules in the *light* category (fast, low-cost processing). Excludes *medium* and *heavy* modules. Use for quick passes or when you want to avoid slower/heavier analyses.
- **Custom** — Lets you pick exactly which modules to run from a multiselect. Only modules that are runnable for the current session (e.g. audio/deps satisfied) are listed.

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

### Group aggregations (v1)

Group runs can produce aggregation modules under:
`outputs/groups/<group_uuid>/<run_id>/<module_name>/`.

v1 group-level aggregation modules:
- NER registry (`ner/`): cross-session entity tables by session and speaker.
- Entity sentiment (`entity_sentiment/`): sentiment framing per entity by session/speaker.
- Topic modeling (`topic_modeling/`): cross-session themes by session and speaker.

Note: v1 recomputes NER at group time to obtain entity types and segment-level
mapping. A future enhancement will store per-segment NER artifacts per transcript
so group aggregation can reuse them directly.

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

Configuration is env-first with explicit overrides. Unknown speakers are excluded from most per-speaker analyses by default. Audio-required modules are gated: defaults include them only when audio is resolvable and required optional deps are available.
Optional voice deps are installed via extras (e.g. `pip install transcriptx[voice]`) when needed.
Downloads are disabled by default; opt in by setting `TRANSCRIPTX_DISABLE_DOWNLOADS=0` and (for transcription models) providing a Hugging Face token or setting the download policy explicitly.

### Gates

Gates are checks that prompt, block, or skip work to keep results accurate and runs predictable.

- Speaker identification gate (CLI): prompts to identify speakers before analysis so per-speaker outputs are meaningful. Can be bypassed via workflow `skip_speaker_gate` or forced non-interactive mode in `check_speaker_gate()`. See `src/transcriptx/cli/speaker_utils.py`.
- Audio/default-module gate: audio-required modules are included in defaults only when audio is resolvable and optional voice deps are available. Override by passing an explicit module list. See `src/transcriptx/core/pipeline/module_registry.py` and `src/transcriptx/core/utils/audio_availability.py`.
- Pipeline requirements gate: modules are skipped when transcript capabilities (segments, timestamps, speaker labels, database) do not meet requirements. See `src/transcriptx/core/pipeline/requirements_resolver.py`.
- Downloads gate: downloads are opt-in via `TRANSCRIPTX_DISABLE_DOWNLOADS=0` (sentiment, emotion, NLP runtime). See `src/transcriptx/core/utils/nlp_runtime.py`.
- Test/CI gates: contributor-only smoke/fast gates keep CI deterministic; see `Makefile` and `tests/README.md`.

## Power users & developers

TranscriptX is built around a DAG-based pipeline, a shared context, and strict artifact contracts. See docs/developer_quickstart.md for extension guidance.

## What’s next

See the roadmap for near-term direction and non-goals.
