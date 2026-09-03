# TranscriptX Architecture

This document gives a high-level mental model for how TranscriptX works today.  
It describes **system shape and typical data flow only** and is **non-authoritative**:  
**All invariants, rules, and behavioral guarantees live in CONTRACT documents.**

**Product definition:** [PRODUCT.md](PRODUCT.md) (what TranscriptX is for).  
**Support policy:** [public_surfaces.md](public_surfaces.md).  
**Evidence snapshot (2026-09-02):** [architecture review](reviews/architecture-review-2026-09-02.md) — reconstruction from the tree; not a contract.

## Core flow

1. Load transcript segments (canonical JSON format).
2. Build an execution plan from the module registry (dependency DAG).
3. Execute modules (light → medium → heavy) with a shared pipeline context.
4. Write artifacts to the run directory and register them in a manifest.
5. Optionally persist run metadata and manifests under the run output directory (and related sidecars).

## Interaction Layers

TranscriptX is structured in two layers:

- **Engine** — Pipeline, modules, and shared context. Responsible for execution and artifact production.
- **GUI** — Streamlit-based web interface (primary product surface). Provides transcript processing, speaker identification, analysis browsing, batch operations, audio preparation, settings, groups, and more.

**High-interaction workspaces (Theme C):** Speakers/Corrections workstation pages may mount Streamlit Components v2 surfaces (`packages/transcriptx_workspaces`) while Streamlit remains the shell. Domain mutations go through shared application services (`app/speaker_id`, `app/corrections`) so legacy fragment UIs and CCv2 bridges cannot drift. See [theme_c_workspaces_ccv2.md](dev/theme_c_workspaces_ccv2.md). A custom non-Streamlit frontend is a post-1.0 escalation (roadmap theme **I**), not current architecture.

Scripting and automation use the Python API directly (`app.workflows`, `core.pipeline`). Transcription is **external**; the GUI may generate commands for external tools rather than running a built-in engine.

Primary surface is the Streamlit GUI; secondary is the typed Python API. Transcription remains external with in-app command generation.

## Components

- **Pipeline** (`src/transcriptx/core/pipeline/`) — Dependency resolution and execution strategy.
- **Analysis modules** (`src/transcriptx/core/analysis/`) — Each module reads from context and writes artifacts.
- **Outputs** — Group-level artifact writing in `src/transcriptx/core/output/`. Run-level artifact registration, output manifest, and display live in `src/transcriptx/core/pipeline/` (manifest_builder, output_reporter). Reproducibility run manifests are in `src/transcriptx/core/utils/run_manifest.py`.
- **GUI** (`src/transcriptx/web/`) — Streamlit UI for analysis, speaker identification, batch operations, settings, and artifact browsing.

## Data loading and outputs (summary)

- **Transcript loading:** Centralized loaders handle JSON transcripts and path resolution. See storage/runtime docs for the full storage contract and helpers.
- **Module output dirs:** Modules write via shared output helpers; full output layout and manifest/run-results contracts are described in `docs/contracts/output-contract-v1.md` and `docs/run_outcome_contract.md`.

For detailed storage roots and directory layout, see `docs/runtime/STORAGE.md`.

## Docker (summary)

- Docker Compose is a supported way to run TranscriptX in containers (no local Python install). See `docs/runtime/docker.md` for compose configuration, volume layout, and environment variables.
- Transcription is external; TranscriptX consumes diarized transcript JSON (see `docs/runtime/transcription.md`).

## Extension points

- Add a module under `src/transcriptx/core/analysis/`, register it in the module registry, and add a minimal test.
- Keep module outputs consistent: JSON/CSV/visual artifacts under the run directory with a stable filename pattern.
- Scripting: use `app.workflows.run_analysis(AnalysisRequest(...))` for automation.

## Boundaries

- **Storage** → `docs/runtime/STORAGE.md`
- **Run truth** → `docs/run_outcome_contract.md`
- **Output layout** → `docs/contracts/output-contract-v1.md`
- **Paths and helpers** → path utilities in `src/transcriptx/core/utils/paths.py` and related modules

Architecture references these contracts but does not restate their rules.

## Related indexes

- [USER_INDEX.md](USER_INDEX.md) · [DEV_INDEX.md](DEV_INDEX.md) · [CONTRACT_INDEX.md](CONTRACT_INDEX.md)
