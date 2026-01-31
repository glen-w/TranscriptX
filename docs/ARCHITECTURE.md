# TranscriptX Architecture (v0.1)

This document gives a high-level mental model for how TranscriptX works today. It is not an API reference.

## Core flow

1. Load transcript segments (canonical JSON format).
2. Build an execution plan from the module registry (dependency DAG).
3. Execute modules (light → medium → heavy) with a shared pipeline context.
4. Write artifacts to the run directory and register them in a manifest.
5. Optionally persist metadata to the database.

## Components

- **CLI** (`src/transcriptx/cli/`)\n  Interactive and non-interactive workflows (Typer).
- **Pipeline** (`src/transcriptx/core/pipeline/`)\n  Dependency resolution and execution strategy.
- **Analysis modules** (`src/transcriptx/core/analysis/`)\n  Each module reads from context and writes artifacts.
- **Outputs** (`src/transcriptx/core/output/`)\n  Standardized artifact writing and run manifest creation.
- **WebUI** (`src/transcriptx/web/`)\n  Streamlit UI that reads run directories under `data/outputs/`.

## Data layout (stable contract)

- `data/recordings/` — input audio
- `data/transcripts/` — transcript JSON outputs
- `data/outputs/` — analysis run outputs
  - `.transcriptx/run_config_effective.json`
  - `manifest.json`
  - module-specific folders

## Extension points (v0.1)

- Add a module under `src/transcriptx/core/analysis/`, register it in the module registry, and add a minimal test.
- Keep module outputs consistent: JSON/CSV/visual artifacts under the run directory with a stable filename pattern.

## Non-goals (v0.1)

- No plugin system
- No hosted services
- No multi-tenant web dashboard
