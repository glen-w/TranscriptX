# Changelog

All notable changes to TranscriptX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1] - 2026-03-25

First supported public contract (v0.1). Artifact schema numbers are unchanged: transcript `schema_version` string `"1.0"`, `run_results.schema_version` integer `2`.

### Added

- Stricter validation: `validate_manifest_shape` requires `manifest_type: artifact_manifest`.
- `RunResultsSummary.validate_run_results` rejects non-dict `modules_skipped` entries.
- Tests for manifest and run_results contract failures.

### Changed

- **Stats output:** only `report.json`, `report.md`, and `report.txt` at run root; removed duplicate `{base}_stats.json` and its manifest registration.
- **Path resolution:** `resolve_file_path` uses `PathResolver` first when available (migration flag removed).
- **Pipeline:** `build_execute_pipeline_context` always returns a validated `PipelineContext` or raises; no legacy execution path when context creation or validation fails.
- **Paths:** removed `TRANSCRIPTX_WAV_STORAGE_DIR` and startup `_migrate_state_paths`; removed module aliases `WAV_STORAGE_DIR` and `WAV_OUTPUT_DIR` (use `PATHS.wav_backup_dir` and `PATHS.recordings_dir`).
- **Requirements:** removed `Requirement.LEGACY_UNUSED` (`database`).
- **Transcript filenames:** canonical check accepts only `*_transcriptx.json` (dropped `*_canonical.json` alias).

### Removed

- `parallel_executor.py` and `TRANSCRIPTX_ENABLE_LEGACY_PARALLEL_EXECUTOR` (`.env.example`).
- `scripts/migrate_speaker_maps.py` and its tests.
- Legacy fixtures `tests/fixtures/whisperx_legacy*.json`; WhisperX adapter tests use `fixtures/transcripts/whisperx/word_level.json`.
- `docs/legacy_transitional_compatibility_register.md`.
- Duplicate stats JSON artifact and deprecated env/migration hooks as above.

### Documentation

- `docs/transcription.md`: golden path emphasizes import + v1.0 runtime contract (no compatibility register link).

