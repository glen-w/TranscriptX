# Changelog

All notable changes to TranscriptX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

(No changes yet.)

## [0.42] - 2026-02-26

### Added
- **ConvoKit Analysis Module**: Added `convokit` module for coordination/accommodation metrics with reply-linking heuristics and standardized artifacts.

### Changed
- **Speaker Map Sidecars Removed**: Speaker maps are now stored only in transcript JSON metadata.
  - Added `extract_speaker_map_from_transcript()` utility for transcript-first mapping access
  - `PipelineContext.get_speaker_map()` prefers transcript metadata, then falls back to segments
  - `save_speaker_map()` and `load_speaker_map()` now raise clear RuntimeError stubs
- **Speaker Map Migration (Phase 2)**: Completed comprehensive migration of remaining speaker_map usage to database-driven approach
  - Updated `file_io.py::write_transcript_files()` to make speaker_map optional and use database-driven extraction
  - Migrated `transcript_output.py` to use `get_unique_speakers()` instead of `load_speaker_map()`
  - Updated `common.py::load_transcript_data()` with deprecation warnings for speaker_map return value
  - Migrated analysis modules: `emotion.py`, `ner.py`, `acts.py` to use `extract_speaker_info()` and `get_speaker_display_name()`
  - Updated pipeline infrastructure: added deprecation warnings to `pipeline_context.get_speaker_map()` and `run_dag_pipeline()` speaker_map parameter
  - Migrated CLI functions: `speaker_management.py` now uses database-driven speaker extraction
  - Added deprecation warnings to `load_speaker_map()` and `load_or_create_speaker_map()` in `speaker_mapping.py`
  - All modules now prioritize `speaker_db_id` from segments for proper speaker disambiguation
  - Speaker information is extracted directly from segments using `speaker_extraction` utilities

### Deprecated
- **Speaker Map Functions**: The following functions are now deprecated and will be removed in a future version:
  - `load_speaker_map()` - Use `extract_speaker_info()` and `get_speaker_display_name()` instead
  - `load_or_create_speaker_map()` - Use `build_speaker_map()` directly for interactive identification
  - `pipeline_context.get_speaker_map()` - Speaker info is available directly from segments
  - `speaker_map` parameter in `run_dag_pipeline()` - No longer needed, extracted from segments
  - `speaker_map` return value from `load_transcript_data()` - Use speaker_extraction utilities instead

### Removed
- **BREAKING**: Removed all deprecated `*_from_file` convenience functions
  - Removed `analyze_sentiment_from_file()`, `analyze_interactions_from_file()`, `analyze_contagion_from_file()`, `analyze_understandability_from_file()`, `analyze_tics_from_file()`, `analyze_emotion_from_file()`, `analyze_entity_sentiment_from_file()`, `analyze_conversation_loops_from_file()`, `analyze_topics_from_file()`, `analyze_semantic_similarity_from_file()`, `analyze_semantic_similarity_advanced_from_file()`, `generate_transcript_output_from_file()`, `analyze_qa_from_file()`, `analyze_temporal_dynamics_from_file()`, `extract_ner_from_file()`, `generate_stats_from_file()`, `generate_wordclouds_from_file()`, `tag_acts_from_file()`, and all related deprecated helper functions
  - All code must now use AnalysisModule classes directly with PipelineContext
  - Migration: Use `{Module}Analysis().run_from_file(path)` or `{Module}Analysis().run_from_context(context)`
- **BREAKING**: Removed `_save_results_legacy()` methods and legacy parameter support
  - Removed `_save_results_legacy()` from base.py and all subclasses
  - `save_results()` now only accepts `output_service` parameter (removed `output_structure` and `base_name`)
  - Removed legacy fallback in `run_from_file()` method
- **BREAKING**: Removed all lazy import wrapper functions from `transcriptx.core.__init__`
  - Removed `tag_acts_from_file()`, `analyze_emotion_from_file()`, `analyze_interactions_from_file()`, `extract_ner_from_file()`, `analyze_sentiment_from_file()`, `generate_stats_from_file()`, `analyze_entity_sentiment_from_file()`, `analyze_conversation_loops_from_file()`, `analyze_topics_from_file()`
  - Updated `__all__` export list to remove these functions
  - Use AnalysisModule classes directly or `run_analysis_pipeline()` instead

### Code Consolidation
- **BREAKING**: Renamed `_save_results_v2()` to `_save_results()` across all analysis modules
  - This is the canonical method name (removed version suffix)
  - All 24+ AnalysisModule subclasses updated
  - Legacy `_save_results_legacy()` methods marked as deprecated (will be removed in v0.4.0)
- **BREAKING**: Consolidated sentiment analysis modules
  - Merged `sentiment_refactored.py` into `sentiment.py` (canonical version)
  - Moved `score_sentiment()` utility function to canonical `sentiment.py`
  - Old `sentiment.py` archived to `scripts/archived/deprecated_modules_backup/`
  - Updated module registry to use canonical `sentiment.py`
- Organized all deprecated `*_from_file` functions with clear section headers
  - Added standard deprecation header to all deprecated functions
  - All deprecated functions now include removal version (v0.4.0)
  - Functions remain functional with `DeprecationWarning` for backward compatibility
- Created archive structure at `scripts/archived/deprecated_code/`
  - Documents deprecated code and migration paths
  - Preserves history while keeping codebase clean
- **Version**: Bumped to 0.42 across pyproject.toml, package __init__, web __init__, setup.py, ROADMAP, and this changelog.

## [0.1.0] - 2026-01-30

### Added
- Public GitHub release baseline with canonical README, ROADMAP, and ARCHITECTURE docs.
- Minimal CI workflow running smoke tests on CPU-only environments.

### Changed
- Fixed console script entrypoint for `transcriptx --help`.
- Standardized version to 0.1.0 across packaging metadata.
- Archived the Sphinx docs tree for v0.1 (README is canonical).

### Security
- Removed secrets from versioned files; tokens are environment-only (`TRANSCRIPTX_HUGGINGFACE_TOKEN` / `HF_TOKEN`).

## [Unreleased]

### Added
- **Run Manifest**: Added mandatory run manifest with config snapshot hash, module metadata, artifact checksums, and rerun mode
- **Diagnostics Commands**: Added `transcriptx doctor` and `transcriptx audit` for reproducibility and integrity checks
- **Analysis CLI**: Added `transcriptx analysis run` with explicit rerun mode flags
- **Guardrail Tests**: Added checks for analysis-module file I/O, repo access, and determinism tiers

### Removed
- **Speaker Map Backward Compatibility**: Completely removed all speaker_map JSON file-based backward compatibility
  - Removed `speaker_map` parameters from all pipeline functions (`pipeline.py`, `dag_pipeline.py`, `pipeline_context.py`)
  - Removed `load_speaker_map()` and `update_transcript_json_with_speaker_names()` functions
  - Removed `load_or_create_speaker_map()` from preprocessing service
  - Removed speaker_map path utility functions (`get_speaker_map_path()`, `get_default_speaker_map_path()`, `validate_speaker_map_path()`, `find_existing_speaker_map()`)
  - Removed deprecated utility functions: `normalize_speaker_id()` from `nlp_utils.py` and `understandability.py`
  - Removed `speaker_map` parameter from `get_display_speaker_name()` in `speaker.py`
  - Removed `speaker_map` parameters from all legacy analysis functions

### Changed
- **Module Results**: Standardized ModuleResult envelope for analysis outputs with metrics, artifacts, and error payloads
- **Artifact Writes**: Centralized artifact writes through atomic writer utilities
- **Rerun Behavior**: Added explicit reuse vs new-run behavior for pipeline execution
- **Speaker Identification**: All speaker identification is now exclusively database-driven via `speaker_db_id` in transcript segments
  - All modules use `extract_speaker_info()` and `get_speaker_display_name()` from `speaker_extraction.py`
  - Modules prioritize `speaker_db_id` from segments for proper speaker disambiguation
  - Speaker information is extracted directly from segments, no JSON file loading required

### Fixed
- **Module Registry**: Fixed recursive `get_available_modules` call in pipeline wrapper
- **Speaker Disambiguation**: Fixed issue where speakers with the same name were not properly distinguished
  - Now uses `speaker_db_id` as canonical identifier for grouping
  - Properly handles multiple speakers with identical names across transcripts

### Testing
- Updated test fixtures in `test_stats.py`, `test_wordclouds.py`, and `test_topic_modeling.py` to use database-driven approach
- Test segments now include `speaker_db_id` instead of relying on speaker_map fixtures

## [0.3.0] - 2025-01-10

### Removed
- **Deprecated Modules**: Removed deprecated utility modules that have been fully migrated:
  - `transcriptx.core_utils` - All functions migrated to organized utility modules:
    - `format_time`, `is_named_speaker` → `transcriptx.utils.text_utils`
    - `suppress_stdout_stderr` → `transcriptx.core.utils.output`
    - `notify_user` → `transcriptx.core.utils.notifications`
  - `transcriptx.io_utils` - All functions migrated to `transcriptx.io` module:
    - `build_speaker_map`, `load_or_create_speaker_map` → `transcriptx.io.speaker_mapping`
    - `load_segments`, `load_transcript`, `save_json`, `save_csv` → `transcriptx.io`
  - `transcriptx.speaker_utils` - All functions migrated to `transcriptx.core.utils.speaker_profiling`

### Changed
- **Module Organization**: Completed migration to organized module structure:
  - All core utilities now in `transcriptx.core.utils.*` submodules
  - All I/O operations now in `transcriptx.io` module
  - All speaker profiling functions now in `transcriptx.core.utils.speaker_profiling`
- **Import Updates**: Updated all imports across codebase to use new module locations:
  - `src/transcriptx/core/analysis/stats.py`
  - `src/transcriptx/core/utils/output_standards.py`
  - `src/transcriptx/core/utils/transcript_output.py`
  - `src/transcriptx/core/utils/nlp_utils.py`
  - `src/transcriptx/core/utils/understandability.py`
  - `src/transcriptx/core/analysis/common.py`
- **Speaker Mapping**: Fully migrated `build_speaker_map` and `load_or_create_speaker_map` implementations from `io_utils` to `io/speaker_mapping.py`

### Migration Notes
- Backups of deprecated modules saved to `scripts/archived/deprecated_modules_backup/`
- All functionality preserved - no breaking changes to public APIs
- All tests should continue to pass with updated imports

## [0.2.1] - 2024-12-19

### Changed
- **Dependency Management**: Updated all documentation to reflect actual dependency structure (`requirements.txt` and `requirements-dev.txt` only)
- **Documentation Cleanup**: Removed references to deleted requirements files (`requirements-core.txt`, `requirements-ml.txt`, `requirements-web.txt`)
- **Project Structure**: Updated README to remove reference to deleted `gui/` directory (web viewer removed)
- **Roadmap Accuracy**: Updated ROADMAP.md to accurately reflect v0.2.0 completion status and v0.3.0 in-progress items
- **WhisperX Documentation**: Updated WHISPERX_INTEGRATION.md with correct CLI command references

### Removed
- **Archived Scripts**: Moved ad hoc/unused scripts to `scripts/archived/`:
  - `run_transcriptx.sh` (duplicates `transcriptx.sh` functionality)
  - `docker-test.sh` (references non-existent docker-compose test profile)
  - `test-docker-setup.sh` (references deleted scripts)
- **Test Documentation**: Created `tests/archived/README.md` documenting removed tests

### Fixed
- **Documentation Consistency**: Ensured README, ROADMAP, and `docs/archived/DEPENDENCY_MANAGEMENT.md` are consistent
- **Infrastructure Verification**: Verified WhisperX Docker infrastructure and CLI menu functionality

## [0.2.0] - 2024-01-XX

### Added
- Comprehensive codebase cleanup and refactoring
- Enhanced deprecation warnings for `io_utils.py` module
- Improved documentation for module migration paths

### Changed
- Updated README.md to reflect v0.2.0 as current stable version
- Removed deprecated `pipeline_old.py` file
- Cleaned up unused imports across analysis modules
- Enhanced deprecation documentation for `io_utils.py` with migration guide

### Fixed
- Fixed undefined `sentiment_dir` variable in `sentiment.py`
- Removed duplicate `create_standard_output_structure` import in `sentiment.py`
- Cleaned up unused imports in multiple analysis modules:
  - `acts.py`: Removed unused `csv`, `json`, and `format_time` imports
  - `base.py`: Removed unused `Path` import
  - `common.py`: Removed unused `Optional` and `create_standard_output_structure` imports
  - `sentiment_refactored.py`: Removed unused `json`, `plt`, and common module imports
  - `understandability.py`: Removed unused `Path` import
  - `conversation_loops.py`: Removed unused `os` import
  - `entity_sentiment.py`: Removed unused `os` import
  - `interactions.py`: Removed unused `os` import

### Deprecated
- `transcriptx.io_utils` module marked for removal in v0.3.0
  - Migration guide provided in module documentation
  - Deprecation warnings added to re-exported functions
  - New code should use `transcriptx.io` module instead

### Removed
- `src/transcriptx/core/pipeline/pipeline_old.py` - Old pipeline implementation (no longer used)

### Code Quality
- Systematic cleanup of unused imports across codebase
- Improved code modularity and consistency
- Enhanced documentation for deprecated modules
- Verified pytest configuration and test suite compatibility

## [0.1.0] - Previous Release

Initial stable release with core functionality:
- Database backend with SQLite
- Docker support
- Enhanced error handling
- Cross-session analysis
- WhisperX integration
- 15+ analysis modules
- Interactive CLI
- Web viewer
- Transcript simplification
- DAG pipeline
- Comprehensive testing

---

## Version History

- **v0.42** (Current): Speaker map migration, module consolidation, run manifest, current release baseline
- **v0.2.0**: Codebase cleanup, import optimization, deprecation management
- **v0.1.0**: Initial stable release


