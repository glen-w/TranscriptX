# TranscriptX Workflows

This document summarizes the main workflows supported by the CLI and how they fit together. For exact commands and options, see [CLI reference](CLI.md). For extension and pipeline structure, see [ARCHITECTURE](ARCHITECTURE.md).

## Workflow overview

| Workflow | Purpose | Main commands |
|----------|---------|----------------|
| **Analysis** | Run analysis modules on one or more transcripts | `analyze`, `test-analysis`, `analysis run` (deprecated alias) |
| **Transcription** | Turn audio into canonical transcript JSON | `transcribe`, (WhisperX via Docker) |
| **Speaker identification** | Map segment labels to named speakers | `identify-speakers` |
| **Audio preprocessing** | Single-file preprocessing (denoise, normalize, etc.) | `preprocess` |
| **Batch audio** | Convert, transcribe, optionally analyze a folder | `batch-process` |
| **WAV / audio utilities** | Convert, merge, compress WAV/MP3/OGG | `process-wav convert`, `process-wav merge`, `process-wav compress` |
| **Deduplication** | Find and remove duplicate files in a folder | `deduplicate` |
| **Simplify transcript** | Remove tics, hesitations, repetitions | `simplify-transcript` |
| **Groups** | Run analysis on a persistent set of transcripts | `group create`, `group run`, `group list`, `group show`, `group delete` |
| **Database** | Init, migrate, speaker profiles, listings | `database init`, `database migrate`, `database list-speakers`, etc. |
| **Cross-session** | Speaker matching and behavior across sessions | `cross-session match-speakers`, `cross-session track-evolution`, etc. |
| **Transcript CRUD** | Store, list, show, export, delete conversations | `transcript store`, `transcript list`, `transcript export`, etc. |
| **Artifacts** | Validate DB ↔ filesystem artifact integrity | `artifacts validate` |
| **Diagnostics** | Environment and run integrity | `doctor`, `audit` |
| **Dependencies** | Optional extras and core mode | `deps status`, `deps install` |
| **Web Viewer** | Browse run outputs (read-only) | `web-viewer` |
| **Settings** | View or edit configuration | `settings --show`, `settings --edit`, `settings --save` |

## Golden paths

1. **Single transcript analysis (non-interactive)**  
   `transcriptx analyze -t /path/to/transcript_transcriptx.json --modules stats --skip-confirm`

2. **Docker: one-off analysis**  
   `docker compose run --rm transcriptx analyze -t /data/transcripts/foo_transcriptx.json --modules stats --skip-confirm`

3. **Group analysis**  
   `transcriptx group create --name "My Set" --type merged_event --transcripts a.json,b.json`  
   `transcriptx group run --identifier "My Set" --modules all`

4. **Interactive menu (default)**  
   `transcriptx` or `transcriptx interactive`

5. **Web Viewer only**  
   `transcriptx web-viewer` (local) or `docker compose up transcriptx-web` (container).

## Configuration and gates

- **Config:** Env-first; override with `--config` or `settings`. See README “Configuration & conventions” and “Environment variables”.
- **Speaker gate:** CLI can prompt to identify speakers before analysis; use `--skip-speaker-identification` in non-interactive flows when appropriate.
- **Core mode:** `--core` / `--no-core` or `TRANSCRIPTX_CORE`; limits modules and disables auto-install when on. See README “Core mode and optional deps”.

## Outputs

Each analysis run writes to a run directory under the configured output root (e.g. `data/outputs/`). Run directories contain a manifest, config snapshots, and module-specific artifacts. Group runs write under `outputs/groups/<group_uuid>/<run_id>/`. See [output_conventions.md](output_conventions.md) and [ARCHITECTURE](ARCHITECTURE.md).
