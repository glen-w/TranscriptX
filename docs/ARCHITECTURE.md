# TranscriptX Architecture

This document gives a high-level mental model for how TranscriptX works today. It is not an API reference.

## Core flow

1. Load transcript segments (canonical JSON format).
2. Build an execution plan from the module registry (dependency DAG).
3. Execute modules (light → medium → heavy) with a shared pipeline context.
4. Write artifacts to the run directory and register them in a manifest.
5. Optionally persist metadata to the database.

## Interaction Layers

TranscriptX is structured in three layers:

- **Engine** — Pipeline, modules, and shared context. Responsible for execution and artifact production.
- **GUI** — Streamlit-based web interface. Provides transcript processing, speaker identification, analysis browsing, batch operations, audio preparation, settings, groups, and more. The GUI and CLI share the same engine and produce identical artifacts.
- **CLI** — Terminal-based orchestration. Supports scripting, automation, and CI pipelines. All GUI workflows have CLI equivalents.

## Components

- **CLI** (`src/transcriptx/cli/`) — Interactive and non-interactive workflows (Typer).
- **Pipeline** (`src/transcriptx/core/pipeline/`) — Dependency resolution and execution strategy.
- **Analysis modules** (`src/transcriptx/core/analysis/`) — Each module reads from context and writes artifacts.
- **Outputs** — Group-level artifact writing in `src/transcriptx/core/output/`. Run-level artifact registration, output manifest, and display live in `src/transcriptx/core/pipeline/` (manifest_builder, output_reporter). Reproducibility run manifests are in `src/transcriptx/core/utils/run_manifest.py`.
- **GUI** (`src/transcriptx/web/`) — Streamlit UI for analysis, speaker identification, batch operations, settings, and artifact browsing. See Interaction Layers.

## Data loading and output layout

- **Transcript loading:** Canonical entry is `TranscriptService` / `io.transcript_loader` (JSON only). Path resolution for missing or renamed files is owned by this layer; callers must not implement their own fallback. VTT must be converted to JSON first (e.g. via `transcript_importer.ensure_json_artifact()`). Naming: `load_transcript_data(transcript_path)` in io/core returns `TranscriptLoadResult` (segments, base_name, transcript_dir, speaker_map) for analysis; `load_transcript_by_session(session_name)` in web loads by session for the viewer; `database_commands.load_transcript_data(Path)` is a CLI helper (Path → full dict with `segments`), with a planned rename to `load_transcript_dict` or migration to the service.
- **Module output dirs:** Analysis modules use `ensure_output_dirs(transcript_path, module_name)` from `_path_core` (via `common.create_module_output_structure`). `OutputStructureBuilder` in `output_structure.py` is deferred/experimental.

## Data layout (stable contract)

- `data/recordings/` — input audio
- `data/transcripts/` — transcript JSON outputs
- `data/outputs/` — analysis run outputs (per-run directories)
  - `manifest.json` (lightweight artifact manifest)
  - `.transcriptx/` (run config, run manifest for reproducibility)
  - module-specific folders

## Docker (runtime / deployment)

**Docker Compose is the recommended way** to run TranscriptX in containers (no local Python install). The same **Engine + GUI + CLI** stack runs inside the image; only the runtime environment changes. The default compose file is at the repo root ([docker-compose.yml](../docker-compose.yml)).

**Transcription is external;** TranscriptX does not run WhisperX or any transcription engine. It consumes diarized transcript JSON (see [transcription.md](transcription.md)).

- **Services (default set):** A plain `docker compose up` starts **transcriptx** (CLI, interactive menu in foreground) and **transcriptx-web** (Streamlit GUI, port 8501). Both mount `./data`; no Docker socket.
- **Image contract:** The image uses `ENTRYPOINT ["transcriptx"]`. You pass the subcommand and arguments directly (e.g. `docker run ... transcriptx:latest analyze ...`). Do not prefix the command with `transcriptx` again.
- **Data:** Mount the host data tree at `/data` so the container sees `data/recordings`, `data/transcripts`, and `data/outputs` in the same layout as the [Data layout](#data-layout-stable-contract) above.
- **Reference:** Build and run details, volume layout, Apple Silicon, permissions, and pitfalls: **[docker.md](docker.md)**.

## Extension points

- Add a module under `src/transcriptx/core/analysis/`, register it in the module registry, and add a minimal test.
- Keep module outputs consistent: JSON/CSV/visual artifacts under the run directory with a stable filename pattern.

## Non-goals

- No plugin system
- No hosted services
- No multi-tenant deployment
