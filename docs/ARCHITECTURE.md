# TranscriptX Architecture (v0.42)

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
- **CLI** — Orchestration and interaction. All run creation, speaker identification, module and preset selection, and group operations happen here.
- **Web Viewer** — Read-only artifact exploration. It browses run outputs under the configured output directories. It does not mutate transcripts and does not create runs.

**Guarantees:** The Web Viewer never mutates transcripts. The Web Viewer never creates runs. All pipeline execution originates in the CLI. This separation preserves reproducibility, determinism, and stable artifact contracts. See [CLI/GUI Strategy](CLI_GUI_STRATEGY.md) for positioning, guardrails, and non-goals.

## Components

- **CLI** (`src/transcriptx/cli/`) — Interactive and non-interactive workflows (Typer).
- **Pipeline** (`src/transcriptx/core/pipeline/`) — Dependency resolution and execution strategy.
- **Analysis modules** (`src/transcriptx/core/analysis/`) — Each module reads from context and writes artifacts.
- **Outputs** — Group-level artifact writing in `src/transcriptx/core/output/`. Run-level artifact registration, output manifest, and display live in `src/transcriptx/core/pipeline/` (manifest_builder, output_reporter). Reproducibility run manifests are in `src/transcriptx/core/utils/run_manifest.py`.
- **Web Viewer** (`src/transcriptx/web/`) — Streamlit UI that reads run directories under `data/outputs/`. Read-only; see Interaction Layers.

## Data layout (stable contract)

- `data/recordings/` — input audio
- `data/transcripts/` — transcript JSON outputs
- `data/outputs/` — analysis run outputs (per-run directories)
  - `manifest.json` (lightweight artifact manifest)
  - `.transcriptx/` (run config, run manifest for reproducibility)
  - module-specific folders

## Docker (runtime / deployment)

**Docker Compose is the recommended way** to run TranscriptX in containers (no local Python install). The same **Engine + CLI + Web Viewer** stack runs inside the image; only the runtime environment changes. The default compose file is at the repo root ([docker-compose.yml](../docker-compose.yml)).

**Orchestration:** The CLI container orchestrates WhisperX via the Docker socket mount (docker exec / Docker API).

- **Services (default set):** A plain `docker compose up` starts all three. **transcriptx** — CLI (interactive menu in foreground); mounts `./data` and the host Docker socket; `depends_on: whisperx`. **whisperx** — WhisperX transcription service (background); used by the CLI via `docker exec`; optional named volume for Hugging Face model cache. **transcriptx-web** — Streamlit viewer (background, port 8501).
- **Image contract:** The image uses `ENTRYPOINT ["transcriptx"]`. You pass the subcommand and arguments directly (e.g. `docker run ... transcriptx:latest analyze ...`). Do not prefix the command with `transcriptx` again.
- **Data:** Mount the host data tree at `/data` so the container sees `data/recordings`, `data/transcripts`, and `data/outputs` in the same layout as the [Data layout](#data-layout-stable-contract) above. All run creation and artifact writing still goes through the CLI; the viewer remains read-only.
- **Reference:** Build and run details, volume layout, Apple Silicon, permissions, and pitfalls: **[docker.md](docker.md)**.

## Extension points (v0.42)

- Add a module under `src/transcriptx/core/analysis/`, register it in the module registry, and add a minimal test.
- Keep module outputs consistent: JSON/CSV/visual artifacts under the run directory with a stable filename pattern.

## Non-goals (v0.42)

- No plugin system
- No hosted services
- No multi-tenant web dashboard
