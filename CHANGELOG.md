# Changelog

All notable changes to TranscriptX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.8.2] - 2026-07-16

### Added

- Broad offline unit coverage for analysis helpers (semantic similarity, wordclouds, acts/affect, corrections, pipeline/output branches) lifting core coverage past 85%.

## [0.3.8.1] - 2026-07-15

### Fixed

- Corrections Studio LLM discovery accepts common local-model JSON shapes (bare candidate arrays, `short_rationale` / related aliases) instead of failing every chunk with `llm_invalid_response`.
- Action-items optional fields coerce common LLM scalar/list mistakes instead of failing the whole parse.
- Artifact file preview no longer crashes on binary files (UTF-8 decode).
- Config default-shape tests isolate `TRANSCRIPTX_*` env from repo `.env` bootstrap.

### Added

- Multi-model LLM response fixture corpus and deeper unit coverage for discovery, narrative, action-items, and summary intake.
- Gated live Ollama diversity helpers/matrix for corrections discovery, overall summary, and speaker summaries.
- Local compose defaults and docs for enabling Corrections Studio LLM against host Ollama.

## [0.3.8] - 2026-07-15

### Added

- Corrections Studio LLM discovery path (`corrections_studio/llm/`) with chunking, grounding, merge, and confidence controls; config via `corrections.llm` / `docs/runtime/corrections-llm.md`.
- Import adapter engine modules for vendor formats (WhisperX, Zoom, SRT/VTT, Otter, Rev, Fireflies, Sembly, generic text).
- FileLock same-thread re-entrancy to avoid Darwin nested-lock self-deadlocks during managed import.

### Changed

- Removed legacy `core/adapters` and `io/adapters` packages in favor of store + `io/import_adapters`.
- Makefile `test-fast` / `test-coverage` marker filters aligned with `pytest.ini` (`legacy`, `semantic_v2_slow`).
- Web composition/layout and public-surface docs updated for current block and entrypoint contracts.

### Fixed

- Blocking FileLock timeouts no longer proceed unlocked; processing-state lock tests use cross-thread contention.
- Version surfaces kept in sync (`transcriptx` / `transcriptx.web`).

## [0.3.7] - 2026-07-14

### Added

- `io/import_metadata/` package (paths, schema, persist, validate, layout) with a thin `import_metadata_sidecar` facade.
- `io/atomic_json.py` for crash-safe JSON writes (re-exported from `rename.io_atomic` for compatibility).
- Mocked-spaCy golden tests characterizing `nlp_utils` preprocess variants before any future split.
- Rename robustness contract tests (lock failure, rollback incomplete, audio classification, speaker-map moves, repair prepared-phase matrix, slug index reconcile).

### Changed

- Managed rename: extracted phase helpers in `plan.py` and `pipeline.py`; migrated remaining production callers off the `file_rename` shim to `rename.*`.
- Consolidated managed import onto `managed_import_workflow`; removed the `import_managed` package.
- Moved import sidecar layout resolution into IO to break the IO↔rename import cycle.

### Fixed

- Library audio-resolution contract tests retargeted to `rename.audio_association` after caller migration.

## [0.3.6] - 2026-07-13

### Added

- Shared `phrase_quality` analyser and theme-phrase resources for deterministic key-theme / highlight / insight phrase filtering.
- Curated Overview blocks (summary hero, at-a-glance, speaker cards, compact highlights/status) and primary-summary precedence across LLM, narrative, and executive summaries.
- Merged **Artifacts** page (Browse / Preview / Export) replacing legacy Data and Explorer routes, with presentation-oriented artifact index and export selection helpers.
- Run-health presentation helpers separating artifact storage health from execution outcomes.

### Changed

- Summary and highlights key-theme extraction prefer noun-led topical phrases and diversity fill over discourse formulas and light-verb constructions.
- Default Overview layout uses the curated Standard profile; Insights gains quieter empty states and related summary blocks.

### Fixed

- Overview composer contract tests updated for curated block IDs; Black/Ruff hygiene on new surfaces.

## [0.3.5] - 2026-07-13

### Added

- Group analysis aggregations for LLM modules (`llm_summary`, `narrative_summary`, `llm_speaker_summary`, `llm_action_items`), `insights`, semantic similarity (legacy/advanced/v2), and voice modules (`voice_mismatch`, `voice_tension`, `voice_fingerprint`).
- Group chart allowlists and generic session-bar wiring for the new aggregations.
- Expanded unit and integration coverage for group infrastructure (output scaffold, artifact merge edges, finalize deps/disabled paths, workflow missing-path branches).

### Changed

- Group module resolution/readiness honors `supports_group` / `for_group` so unsupported modules are filtered from group runs.
- Prosody/group dashboard summary keys use session-prefixed fields for safer multi-transcript aggregation.

### Fixed

- Pre-release hygiene: document optional Streamlit perf env vars; ignore `.env.*` (keep `.env.example`) and `data/perf/`; stop tracking large streamlit load-profile JSONL.

## [0.3.4] - 2026-07-13

### Added

- `llm_action_items` analysis module: structured Ollama extraction of action items (owner, deadline, status, quote) with quote grounding, dedupe, and distinct cache identity.
- `analysis.llm_action_items.effort` config (low/medium/high/max; default `high`).
- Insights/executive UI blocks and zip-export summary section for action items.
- `lexical_diversity` analysis module: deterministic TTR, MTLD, and hapax-rate metrics (optional time buckets), CSV/JSON artifacts, and chart gallery entries.
- Insights block and overview summary extractor for lexical diversity; group aggregation allowlist for descriptive session metrics.

## [0.3.3] - 2026-07-13

### Added

- `llm_speaker_summary` analysis module: abstractive Ollama summaries for each named speaker, with per-speaker artifacts and a global index.
- `analysis.llm_speaker_summary.effort` config (low/medium/high/max), mirroring `llm_summary` effort tiers.
- Insights block for per-speaker LLM summaries.

## [0.3.2] - 2026-07-02

### Added

- `analysis.llm_summary.effort` config (low/medium/high/max) with builtin Ollama profiles for input size, timeout, and output tokens.
- Pydantic pilot for `llm_summary` settings and integration tests with golden fixtures.
- Input coverage metadata in llm_summary provenance.

### Changed

- `llm_summary` uses effort-tier runtime resolution instead of global `llm.max_input_chars` / `max_output_tokens` on the Ollama path.
- Dockerfile builds the wheel after spaCy/NLTK/TextBlob downloads so NLP assets are baked into the image.
- Transcript viewer segment timestamps render with millisecond precision when sub-second.

### Removed

- `speaker_profiling` utility and its unit tests (unused).

## [0.3.1] - 2026-07-02

### Added

- Config delegation tests and golden fixtures for pauses, voice, and corrections settings.
- Contract tests for stale surface references and expanded unit coverage (lazy imports, perf instrumentation, voice skip paths).

### Changed

- `src/transcriptx/web/streamlit_app.py` is now a deprecation stub. Use `transcriptx`, `python -m transcriptx.web`, or `streamlit run src/transcriptx/web/app.py`.
- Analysis config helpers delegate pauses, voice, and corrections to dedicated Pydantic pilots.
- Dependency pins: `watchdog==5.0.3` (dagster-compatible), `marshmallow==4.1.2` and `scikit-learn==1.5.0` aligned across `pyproject.toml` and `requirements.txt`.

### Removed

- Tracked pre-release report artifacts under `artifacts/pre-release/` and `reports/pre_release*/` (now gitignored).

## [0.3.0] - 2026-07-02

### Added

- Module registry snapshot and contract tests with golden fixture for 39 modules.
- Domain-split module definition builders under `module_specs/` composed via explicit `MODULE_REGISTRY_ORDER`.

### Changed

- `build_module_definitions` in `module_registry_specs.py` is now a thin compatibility wrapper; `MODULE_CLASS_MAP` and `EXTRA_REPRESENTATIVE` remain on the public façade.

## [0.2.0] - 2026-06-17

### Added

- Local LLM integration via Ollama (`llm_summary`, `narrative_summary` opt-in modules).
- `LLMConfig`, env/file overrides, `requires_llm` gating, and stable `error_code` propagation through the DAG adapter.
- Shared LLM helpers (truncation, provenance, artifact staging) and documentation (`docs/runtime/llm.md`).

## [0.1.2] - 2026-06-17

### Fixed

- Declare `networkx` as a core package dependency so wheel installs can build the module registry (conversation-loops and network chart renderers import it at load time).
- Defer analysis module class imports until execution so optional extras (e.g. maps/NLP) are not required to plan or run unrelated modules such as `stats`.
- Document `TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS` in `.env.example`.

### Added

- Multi-language transcript import: flat `{base}_{lang}.json` variants (e.g. `meeting_fr.json`) inherit the base transcript's speaker map on managed import when the base has a speaker-map sidecar and the variant does not (`io/speaker_map_inheritance.py`, `core/utils/transcript_variant_paths.py`). `speaker_id_to_db_id` is copied because those IDs are canonical cross-segment grouping keys shared by the same physical speakers.
- Combined Overview export: a single self-contained `index.html` (`utils/export_index.py`) that server-renders a transcript view plus an unfiltered charts gallery so exports open correctly over `file://` (no client-side `fetch()` of local JSON). The transcript and charts sections fail independently. Inline, CDN-free CSS and chart-section rendering are shared with the charts-only export (`utils/charts_export.py`).
- `semantic_similarity_v2` analyzer package (intake, candidates, embedding, similarity, cluster, classify, output, diagnostics, visualization); `momentum` and `qa_analysis` now consume its results with fallback to the legacy variants.
- SRT writer for transcript segments (`io/srt_writer.py`).

### Changed

- Pipeline (DAG) internals decomposed from the monolithic `dag_pipeline.py` into focused modules (contracts/ports DTOs, `dag_planner`, `dag_executor`, `dag_execution_adapter`, `run_orchestrator`, `run_bootstrap`, `run_configurator`, `run_persistence`, `run_presenter`, `run_outcome`, `run_workspace`) with file-backed store/reporter adapters behind ports. Legacy compatibility shims preserve existing callers.
- Chart fixes for modules that were not rendering on diarized-but-unnamed transcripts: `echoes` falls back to the raw diarization label (e.g. `SPEAKER_00`) when no human-readable name exists and accepts a configurable embedding model; the contagion matrix uses `is_turn_taking_speaker_label` instead of `is_named_speaker`.
- Matplotlib rendering split into a `core/viz/mpl` package with per-type renderers (bar, box, heatmap, line, network, scatter) and a dispatcher.
- Web UI decomposed: `web/app.py` split into `router`, `navigation`, `sidebar` (+ state/options), `page_flash`, and view-state helpers, plus a `transcript_viewer` package (segments, highlight, metadata, downloads, modules panel, preflight).
- `speaker_map_resolver`: placeholder self-maps (e.g. `SPEAKER_00 -> SPEAKER_00`) are treated as still-unnamed via `is_effective_speaker_name`, so UI progress and pipeline gating do not count them as identified speakers.
- Stats summary lifecycle cleanup: `create_comprehensive_summary` is the maintained plain-text summary helper, now split into section renderers without output-schema/heading drift.
- Legacy HTML export path `generate_enhanced_html_summary` is retained for temporary manual compatibility and now emits a deprecation warning pointing users to `report.json`/`report.md`/`report.txt`.
- Config env override handling is now unified under a canonical registry (`env_key_registry.apply_env_to_config`) used by both `env_overrides.apply_transcriptx_env` and `system_env.apply_env_overrides`. This intentionally adds previously missing `system`-path coverage for `TRANSCRIPTX_CORE`, `TRANSCRIPTX_FILE_SELECTION_MODE`, semantic/module progress interval keys, and `TRANSCRIPTX_SPEAKER_GATE_*` keys.
- Added opt-in strict unknown env enforcement with `TRANSCRIPTX_CONFIG_STRICT=1`: unknown `TRANSCRIPTX_*` keys now raise `ConfigLoadError` in strict mode; default mode logs a diagnostic warning while preserving mutation/error behavior.

### Removed

- Removed dead `generate_summary_stats` from `stats/summary.py` (no supported call sites; stale unresolved dependencies).

### Dependencies

- **Security:** bumped `cryptography` 46.0.6 → 48.0.1 (PYSEC-2026-36, GHSA-537c-gmf6-5ccf) and `python-dotenv` 1.1.1 → 1.2.2 (CVE-2026-28684). `cryptography` is a transitive/security pin (not imported directly); `python-dotenv` is used only via the stable `load_dotenv` API. `setuptools` remains capped `>=64,<70` for llvmlite/numba build compatibility; the remaining setuptools advisories are build-time only and blocked by that cap.

## [0.1.1] - 2026-04-06

### Changed

- Code style: Black formatting across touched modules; Ruff fix (remove unused variable in corrections studio fuzzy speaker inputs).
- **Pytest:** register the `optional` marker in `pytest.ini` so release-profile expressions such as `not optional and not heavy and not quarantined` match project policy.
- **README:** document the canonical development sample transcript (`tests/fixtures/mini_transcript.json`) and how it relates to `scripts/docker-smoke-test.sh`.

### Dependencies

- **Typer:** use `typer==0.16.0` without the `[all]` extra. Pip warned that 0.16.0 does not ship that extra name; runtime behavior for the `transcriptx` launcher is unchanged because Rich and Click are already direct dependencies and the CLI surface is minimal.
- **Security-related pins:** `cryptography` 46.0.6, `nltk` 3.9.4 (addresses published advisories for the previous pins).

**Note for upgrades:** If you install from a custom constraints file, an air-gapped mirror, or a monorepo lockfile, re-resolve dependencies after this release. Mixed pins (e.g. an older `cryptography` forced by another package) can make `pip check` or Docker builds fail until constraints are aligned.

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

