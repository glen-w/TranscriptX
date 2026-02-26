# TranscriptX CLI Reference

This document describes the TranscriptX command-line interface. All flags and options match the current `transcriptx --help` and per-command `--help` output. Run `transcriptx <command> --help` for the latest options.

## Global options

Available on the main entrypoint:

| Option | Short | Description |
|--------|-------|-------------|
| `--config` | `-c` | Path to configuration file |
| `--log-level` | | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `--output-dir` | `-o` | Custom output directory |
| `--core` | | Force core mode (only core modules, no auto-install of optional deps) |
| `--no-core` | | Disable core mode (all modules, allow auto-install) |
| `--help` | | Show help and exit |

---

## Command tree

| Command | Description |
|--------|-------------|
| `web-viewer` | Launch the Streamlit web viewer interface |
| `analyze` | Analyze a transcript file with specified modules and settings |
| `transcribe` | Transcribe an audio file using WhisperX |
| `identify-speakers` | Identify speakers in a transcript file |
| `preprocess` | Run audio preprocessing on a single file (MP3, WAV, etc.) |
| `batch-process` | Batch process audio: convert, transcribe, detect type, extract tags |
| `deduplicate` | Find and remove duplicate files in a folder |
| `simplify-transcript` | Simplify transcript (remove tics, hesitations, etc.) |
| `interactive` | Launch the interactive menu (default when run with no arguments) |
| `settings` | Manage settings via flags (show/edit/save) |
| `test-analysis` | Run test analysis via flags (non-interactive) |
| `whisperx-web-gui` | Manage WhisperX Web GUI stack via flags |
| `database` | Database management commands |
| `cross-session` | Cross-session speaker tracking commands |
| `transcript` | Transcript management commands |
| `artifacts` | Artifact validation commands |
| `group` | TranscriptSet group commands |
| `perf` | Performance span queries |
| `analysis` | Analysis commands (includes deprecated `run` alias) |
| `deps` | Optional dependency status and install (extras) |
| `doctor` | Diagnostics commands |
| `audit` | Audit pipeline runs |
| `process-wav` | Process audio: convert, merge, or compress (WAV, MP3, OGG, etc.) |

---

## Commands (detail)

### web-viewer

Launch the Streamlit web viewer interface.

**Options:** `--host`, `--port` (default 8501), `--help`.

**Example:** `transcriptx web-viewer --port 8501`

---

### analyze

Analyze a transcript file with specified modules and settings.

| Option | Short | Description |
|--------|-------|-------------|
| `--transcript-file` | `-t` | Path to transcript JSON file |
| `--transcripts` | | Analyze multiple transcripts as a group (repeat for each file) |
| `--all-transcripts` | | Analyze all available transcript JSON files |
| `--mode` | `-m` | Analysis mode: quick or full [default: quick] |
| `--modules` | | Comma-separated list of modules or 'all' [default: all] |
| `--profile` | | Semantic profile for full mode: balanced, academic, business, casual, technical, interview |
| `--skip-confirm` | | Skip confirmation prompts |
| `--output-dir` | `-o` | Custom output directory |
| `--include-unidentified-speakers` | | Include unidentified speakers in per-speaker outputs |
| `--anonymise-speakers` | | Anonymise speaker display names in outputs |
| `--skip-speaker-identification` | | Skip the speaker identification gate |
| `--non-interactive` | | Run in non-interactive mode (skip all prompts) |
| `--persist` | | Persist run metadata and artifacts to DB |

**Canonical filenames:** Analysis expects `*_transcriptx.json` by default. For other filenames, see [docker.md](docker.md) (canonical filename and `--accept-noncanonical`).

**Examples:**

```bash
transcriptx analyze -t /path/to/meeting_transcriptx.json --modules stats --skip-confirm
transcriptx analyze -t ./transcript_transcriptx.json --mode full --output-dir ./out
```

---

### transcribe

Transcribe an audio file using WhisperX.

| Option | Short | Description |
|--------|-------|-------------|
| `--audio-file` | `-a` | Path to audio file [required] |
| `--engine` | | Transcription engine: auto or whisperx [default: auto] |
| `--analyze` | | Run analysis after transcription |
| `--analysis-mode` | `-m` | Analysis mode if --analyze: quick or full [default: quick] |
| `--analysis-modules` | | Comma-separated list of modules or 'all' [default: all] |
| `--skip-confirm` | | Skip confirmation prompts |
| `--print-output-json-path` | | Print only the transcript JSON path to stdout |

**Example:** `transcriptx transcribe -a recording.wav --analyze --skip-confirm`

---

### identify-speakers

Identify speakers in a transcript file.

| Option | Short | Description |
|--------|-------|-------------|
| `--transcript-file` | `-t` | Path to transcript JSON file [required] |
| `--overwrite` | | Overwrite existing speaker identification without confirmation |
| `--skip-rename` | | Skip transcript rename after speaker identification |

---

### preprocess

Run audio preprocessing on a single file (MP3, WAV, or other supported format).

| Option | Short | Description |
|--------|-------|-------------|
| `--file` | `-f` | Path to audio file [required] |
| `--output` | `-o` | Output path (default: same dir, stem_preprocessed.<ext>) |
| `--skip-confirm` | | Skip confirmation if output exists |

---

### batch-process

Batch process audio files: convert to MP3, transcribe, detect type, and extract tags.

| Option | Short | Description |
|--------|-------|-------------|
| `--folder` | | Path to folder containing audio files [required] |
| `--size-filter` | | Filter by size: all, small (&lt;30MB), or large (≥30MB) [default: all] |
| `--files` | `-f` | Comma-separated list of specific files to process |
| `--resume` | | Resume from checkpoint if available |
| `--clear-checkpoint` | | Clear existing checkpoint before processing |
| `--move-wavs` | | Move WAV files to storage after processing |
| `--identify-speakers` | | Run speaker identification after processing |
| `--analyze` | | Run analysis pipeline after processing |
| `--analysis-mode` | | Analysis mode if --analyze [default: quick] |
| `--skip-confirm` | | Skip confirmation prompts |

---

### deduplicate

Find and remove duplicate files in a folder.

| Option | Short | Description |
|--------|-------|-------------|
| `--folder` | | Path to folder to scan for duplicates [required] |
| `--files` | `-f` | Comma-separated list of specific files to delete |
| `--auto-delete` | | Automatically delete duplicates without interactive review (requires --files) |
| `--skip-confirm` | | Skip confirmation prompts (only with --auto-delete) |

---

### simplify-transcript

Simplify a transcript by removing tics, hesitations, repetitions, and agreements.

| Option | Short | Description |
|--------|-------|-------------|
| `--input-file` | `-i` | Path to input transcript JSON file [required] |
| `--output-file` | `-o` | Path to output simplified transcript JSON file [required] |
| `--tics-file` | | Path to JSON file with list of tics/hesitations |
| `--agreements-file` | | Path to JSON file with list of agreement phrases |

---

### interactive

Launch the interactive menu (default when run with no arguments). Options: `--config`, `--log-level`, `--output-dir`, `--help`.

---

### settings

Manage settings via flags. Options: `--show`, `--edit`, `--save`, `--help`.

---

### test-analysis

Run test analysis via flags (non-interactive). Options: `--transcript` / `-t`, `--mode` / `-m`, `--modules`, `--profile`, `--skip-confirm`, `--output-dir` / `-o`, `--help`.

---

### whisperx-web-gui

Manage WhisperX Web GUI stack. Options: `--action` (start or stop, default start), `--open-browser`, `--help`.

---

### database

Database management commands.

| Subcommand | Description |
|------------|-------------|
| `reset` | Reset the database (dev-only) |
| `init` | Initialize the TranscriptX database |
| `status` | Display database status and information |
| `migrate` | Manage database migrations |
| `history` | Display migration history |
| `profile-speaker` | Create or update a speaker profile from transcript data |
| `list-speakers` | List all speakers in the database |
| `speakers-list` | List all speakers with their statistics |
| `speakers-show` | Show detailed information about a speaker |
| `speakers-merge` | Merge two speakers into one |
| `speakers-stats` | Show aggregate speaker statistics |

Run `transcriptx database <subcommand> --help` for options.

---

### cross-session

Cross-session speaker tracking commands.

| Subcommand | Description |
|------------|-------------|
| `match-speakers` | Find potential matches for a speaker across all sessions |
| `track-evolution` | Track behavioral pattern evolution for a speaker |
| `detect-anomalies` | Detect behavioral anomalies for a speaker |
| `create-cluster` | Create a new speaker cluster |
| `add-to-cluster` | Add a speaker to a cluster |
| `show-network` | Show the interaction network for a speaker |
| `list-clusters` | List all speaker clusters |

---

### transcript

Transcript management commands.

| Subcommand | Description |
|------------|-------------|
| `list` | List all conversations in the database |
| `show` | Show detailed information about a conversation |
| `delete` | Delete a conversation and all associated data |
| `export` | Export conversation data to JSON file |
| `store` | Store a transcript file in the database |
| `status` | Show database status and statistics |

---

### artifacts

Artifact validation commands.

| Subcommand | Description |
|------------|-------------|
| `validate` | Validate DB ↔ FS artifact integrity and provenance |

---

### group

TranscriptSet group commands.

| Subcommand | Description |
|------------|-------------|
| `create` | Create a group (or return existing by deterministic key) |
| `list` | List persisted groups |
| `show` | Show details for a group |
| `run` | Run analysis for a persisted group |
| `delete` | Delete a group |

**Examples:**

```bash
transcriptx group create --name "Workshop 2026-02" --type merged_event --transcripts /path/a.json,/path/b.json
transcriptx group list --type merged_event
transcriptx group run --identifier <uuid-or-key-or-name> --modules all
```

---

### perf

Performance span queries. Subcommand: `top` (show top span groups by duration statistics).

---

### analysis

Analysis commands. Subcommand: `run` — deprecated alias for `transcriptx analyze`. Prefer `transcriptx analyze` directly.

---

### deps

Optional dependency status and install (extras).

| Subcommand | Description |
|------------|-------------|
| `status` | Show which extras are available or missing and current core_mode |
| `install` | Install optional dependencies. Use --full for all extras, or list extras (voice emotion nlp ...) |

**Example:** `transcriptx deps install voice emotion nlp`

---

### doctor

Run environment and configuration diagnostics. Options: `--json` (emit JSON report), `--help`.

**Example:** `transcriptx doctor`

---

### audit

Audit a PipelineRun for artifact integrity and manifest coverage.

| Option | Short | Description |
|--------|-------|-------------|
| `--run-id` | `-r` | PipelineRun ID to audit [required] |
| `--json` | | Emit JSON report |

**Example:** `transcriptx audit -r 42`

---

### process-wav

Process audio files: convert, merge, or compress (WAV, MP3, OGG, etc.).

| Subcommand | Description |
|------------|-------------|
| `convert` | Convert audio files to MP3 |
| `merge` | Merge multiple audio files into one MP3 file |
| `compress` | Compress WAV files in backups directory into zip archives |

**Examples:**

```bash
transcriptx process-wav convert --input file.wav --output file.mp3
transcriptx process-wav merge --inputs a.wav b.wav --output combined.mp3
transcriptx process-wav compress
```

---

## Source of truth

CLI flags and options in this document are derived from the current `transcriptx` and `transcriptx <command> --help` output. When in doubt, run `transcriptx <command> --help` locally.
