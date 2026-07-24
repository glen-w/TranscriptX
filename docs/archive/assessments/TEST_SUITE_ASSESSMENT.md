> **Archived / superseded.** Historical context only. Current authority: [README.md](../../../tests/README.md). Do not treat as live roadmap or support policy.

# Pytest Suite Assessment

> **Historical (2026-02-02).** Do **not** treat counts, quarantines, or backlog rows below as current truth. Prefer [`docs/dev/stocktake_2026-07-17.md`](../docs/dev/stocktake_2026-07-17.md) §7, Makefile lanes, and live `pytest --collect-only`. Streamlit GUI testing posture: [`docs/dev/streamlit_ui_test_assessment_2026-07-18.md`](../docs/dev/streamlit_ui_test_assessment_2026-07-18.md).

**Date:** 2026-02-02  
**Scope:** Assess suite, quarantine obsolete tests, add high-leverage unit and integration tests.

**Related (Streamlit GUI testing posture, 2026-07-18):** [`docs/dev/streamlit_ui_test_assessment_2026-07-18.md`](../docs/dev/streamlit_ui_test_assessment_2026-07-18.md) — surface × layer matrix, journey risk scores, doubles-first strategy, P0–P2 backlog. This living doc remains the expansion history; that assessment is the dedicated Streamlit UI test gap report.

---

## 1. Suite overview

- **Collected:** ~1558 tests (3 skipped at collection for missing modules).
- **Structure:** `tests/analysis/`, `tests/core/`, `tests/integration/`, `tests/io/`, `tests/pipeline/`, `tests/contracts/`, `tests/regression/`, `tests/smoke/`, `tests/unit/`, `tests/utils/`, `tests/web/`, etc. (legacy `tests/cli/` and DB-specific trees removed.)
- **Markers:** `smoke`, `unit`, `integration`, `contract`, `slow`, `requires_models`, `requires_docker`, `quarantined`, `integration_core`, `integration_extended`, etc.

---

## 2. Legacy CLI tests (removed)

Legacy CLI test files that targeted removed or renamed APIs (e.g. `select_transcript_file_interactive`, `settings_menu_loop`, `db_reset_command`, `CrossSessionTrackingService`) have been **removed**. The tree no longer contains a `tests/cli/` directory; the product entry is web GUI and Python API. No quarantined CLI tests remain.

---

## 3. Skipped at collection (missing modules)

- `tests/analysis/test_rules.py` – `transcriptx.core.analysis.rules` not found.

Any other skipped-at-collection tests (e.g. missing modules) remain in the tree; fix or remove when the corresponding modules are (re)introduced or deprecated.

---

## 4. High-leverage tests added

### Unit (`tests/unit/test_high_leverage.py`)

- **Config lifecycle:** `get_config` returns `TranscriptXConfig`, has required sections; `set_config` updates global; `load_config(path)` loads JSON and sets global.
- **Validation:** `validate_transcript_file("")` raises; `validate_segment` raises for missing `text`/`speaker`, non-dict segment.
- **Module registry:** `get_available_modules` non-empty; `stats` available and `get_module_function("stats")` callable; `get_module_info` / `get_dependencies` return expected types.
- **Transcript loader:** `load_segments` with `{"segments": []}` returns `[]`; direct list root JSON loads correctly.

### Integration (`tests/integration/core/test_high_leverage_integration.py`)

- **Pipeline + stats:** `run_analysis_pipeline` with `selected_modules=["stats"]` on `tests/fixtures/mini_transcript.json`; assert no errors, `output_dir` exists, `manifest.json` has `artifacts`.
- **Pipeline + transcript_output:** Same with `transcript_output`; assert transcript outputs (txt/csv) under output dir.

Both integration tests use `@pytest.mark.integration_core`, tmp paths, and env/monkeypatch so they do not require DB or external services.

---

## 5. Recommendations

1. **Default run:** Keep `addopts = ... -m "not quarantined"` so normal/CI runs are green.
2. **Quarantine cleanup:** When CLI APIs stabilize, either update the quarantined tests to the new APIs or remove them and delete the marker.
3. **Missing modules:** Either reintroduce `transcriptx.core.analysis.rules` and `transcriptx.cli.audio_utils` or delete/skip the tests that depend on them.
4. **High-leverage coverage:** The new unit tests cover config, validation, module registry, and loader; the new integration tests cover a minimal pipeline run. Add more of the same style for other critical paths (e.g. state persistence, output builder) as needed.

---

## 6. Expansion (2026-03-06)

### Bug fix

- **`tests/core/utils/test_performance.py`** – `test_performance_estimator_no_transcription_method` was failing because it instantiated `PerformanceEstimator` and called `estimate_pipeline_time` without mocking the DB session, hitting a missing `performance_spans` table. Fixed by adding `db_session_factory` fixture and patching `get_session`.

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_state_schema.py` | 35 | `validate_state_entry` (valid, missing fields, invalid status/timestamps, module subset checks), `migrate_state_entry` (defaults, preserves existing, infers status), `validate_state_paths` (existing/missing/None paths), `enrich_state_entry` (timestamps, immutability), `update_analysis_state` (completed/partial/failed/empty runs, timestamps, immutability), `get_analysis_status` (not_started/completed/partial, pending calculation, all keys) |
| `tests/unit/test_manifest_loader.py` | 13 | `load_artifact_manifest` (valid, backward compat, wrong type, not-object, missing file, invalid JSON, string path), `load_run_manifest` (valid, backward compat, wrong type, not-object, missing file, string path) |
| `tests/unit/test_output_standards.py` | 16 | `create_standard_output_structure` (return type, dir layout, data/charts dirs, namespace/version overrides, redirect non-OUTPUTS_DIR), `get_standard_file_patterns` (keys, base_name, module_name), `cleanup_empty_directories` (empty/nonempty/mixed/nonexistent), `cleanup_module_outputs`, `OutputStructure` dataclass |

### Suite totals after expansion

- **Default run:** 1320 passed, 3 skipped, 458 deselected, 0 failed.
- **Full collection:** ~1781 tests (1717 + 64 new).

---

## 7. Expansion (2026-03-06) – test review and path fix

### Bug fix

- **`src/transcriptx/core/utils/_path_core.py`** – `get_transcript_dir` and `get_group_output_dir` used `OUTPUTS_DIR` / `GROUP_OUTPUTS_DIR` with `/`; when tests monkeypatch these to `str(tmp_path)`, Python raised `TypeError: unsupported operand type(s) for /: 'str' and 'str'`. Fixed by normalizing to `Path(OUTPUTS_DIR)` and `Path(GROUP_OUTPUTS_DIR)` before joining.
- **`tests/unit/test_path_utils.py`** – `test_get_enriched_transcript_path_uses_standard_layout` and `test_ensure_output_dirs_contract` now pass.

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_run_schema.py` | 11 | `RunManifestInput.from_cli_kwargs` (minimal, with modules/options), `RunManifestInput.from_file` (valid, config_overrides None, missing file), `RunResultsSummary.validate_run_results` (minimal, modules_skipped normalization), `validate_manifest_shape` (valid artifact, wrong type raises, backward compat no manifest_type) |

### New contract test

| File | Test | Covers |
|------|------|--------|
| `tests/contracts/test_run_results_and_manifest_contracts.py` | `test_single_pipeline_result_shape_contract` | Single-transcript `run_analysis_pipeline()` return dict must contain `REQUIRED_SINGLE_RESULT_KEYS` (output_dir, errors, transcript_path, etc.). |

---

## 8. Expansion (2026-03-08) – suite review and high-leverage run results

### Bug fix

- **`tests/core/utils/test_performance.py`** – `test_logs_span_execution` and `test_logs_exception_event` were failing because the global `PerformanceLogger` singleton could be disabled (`_disabled=True`) by an earlier test that hit a missing `performance_spans` table. Fixed by using a fresh `PerformanceLogger()` and passing it as `logger_instance=logger` to `TimedJob` so the test does not depend on global state.

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/pipeline/test_manifest_builder.py` | `TestBuildRunResultsSummary` (5 tests), `test_write_run_results_summary_creates_file` | `build_run_results_summary` (minimal payload, skipped/failed computation, preset_explanation, errors); `write_run_results_summary` (writes `run_results.json`, contract with `RunResultsSummary.validate_run_results`) |

### Suite totals after expansion

- **Default run:** 1359 passed, 3 skipped, 458 deselected, 0 failed.
- **High-leverage:** Run results summary builder and run_results.json write path now have direct unit tests and schema contract.

### integration_core fixes (2026-03-08)

- **`src/transcriptx/core/utils/transcript_output.py`** – Normalized `OUTPUTS_DIR` and `DIARISED_TRANSCRIPTS_DIR` to `Path(...)` before `.resolve()` and `/` so tests that monkeypatch them to `str(tmp_path)` do not raise `AttributeError: 'str' object has no attribute 'resolve'`.
- **`tests/integration/core/test_cli_workflow_integration.py`** – Patches were targeting `transcriptx.cli.main.questionary` but `main` is a module (main.py), not a package. Updated to patch `transcriptx.cli.interactive_menu.questionary.select` where questionary is actually used.
- **Result:** `pytest -m integration_core` now passes (32 passed).

---

## 10. Expansion (2026-03-10) – progress snapshot and merge workflow coverage

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_progress_snapshot.py` | 31 | `make_initial_snapshot` (status, phase, total, counts, logs, error, current_module); `_refresh_pct` (no-total no-raise, correct formula, capped at 100); `update_snapshot_from_event` (all 7 event types, log_line appended, log cap, unknown-event no-op); `SnapshotLogHandler.emit` (append, missing-key init, WARNING sets latest_event, INFO does not, cap at 100); `NullProgress` (protocol conformance, all methods callable) |
| `tests/app/test_merge_workflow.py` | 20 | `run_merge` validation (ffmpeg unavailable, <2 files, duplicates, missing files, bad extension, output exists without overwrite, output same as input); output filename derivation (explicit no-.mp3 gets extension, date-prefix auto-name, fallback when no prefix); happy path (success result shape, merge exception → failed result, 4 stages called, NullProgress no-raise); backup branch (empty backup adds warning, backup exception adds warning + merge continues); `MergeController` delegation (validation failure, success, unexpected exception → WorkflowExecutionError) |

### Suite totals after expansion

- **Default run:** 1589 passed, 3 skipped, 321 deselected, 0 failed.
- **New coverage areas:** `app.progress` (snapshot state machine, SnapshotLogHandler, NullProgress protocol) and `app.workflows.merge` + `app.controllers.merge_controller` were entirely untested.

---

## 9. Expansion (2026-03-09) – state query helper coverage

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_state_utils_queries.py` | 6 | `list_transcripts_with_analysis` filtering; `list_transcripts_needing_analysis` with/without module filters; `has_analysis_completed` fallback branch; `get_missing_modules` no-history fallback; `get_analysis_history` not-found path |

### Suite totals after expansion

- **Default run:** 1380 passed, 3 skipped, 458 deselected, 0 failed.
- **integration_core:** 32 passed.

---

## 11. Expansion (2026-03-11) – manifest contract, state repair, pipeline result shape

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_run_schema.py` | 2 | `validate_manifest_shape` with one artifact entry (required keys id, kind, rel_path, bytes, mtime, mime, tags, module); optional scope/speaker on artifact entry |
| `tests/core/utils/test_state_management.py` | 2 | `repair_processing_state` on nonexistent file returns early with repaired=False, no backup; dry_run=True does not write to state file |

### New contract test

| File | Test | Covers |
|------|------|--------|
| `tests/contracts/test_run_results_and_manifest_contracts.py` | `test_pipeline_result_shape_contract_with_empty_modules` | Run with `selected_modules=[]` still returns result with `REQUIRED_SINGLE_RESULT_KEYS` and `modules_run == []` (stable result shape on no-op run) |

### Suite totals after expansion

- **Default run:** 1717 passed, 5 skipped, 321 deselected, 0 failed.
- **Collected (default filter):** 1722 selected (2043 total, 321 deselected).

---

## 12. Expansion (2026-03-12) – processing state load/save unit tests

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/utils/test_processing_state.py` | 5 | `load_processing_state` (nonexistent → empty dict; valid JSON → parsed; locked → empty); `save_processing_state` (creates file with state); load/save roundtrip. Uses tmp_path and mocked FileLock/create_backup so tests run in default suite. |

### High-leverage area

- **State persistence:** Direct unit coverage for `processing_state.load_processing_state` and `save_processing_state` (previously only covered via integration/regression and state_utils/state_backup).

---

## 13. Expansion (2026-03-12) – per-module smoke tests

### New smoke tests

| File | Purpose |
|------|---------|
| `tests/smoke/test_all_modules_smoke.py` | Per-module pipeline smoke: runs `run_analysis_pipeline` with a single module on `mini_transcript.json`. **Core-available non-audio modules** are parameterized and always run; **required-extras modules** are covered by a separate test path that runs when extras are installed. Modules that need larger data or NLTK (topic_modeling, understandability) are excluded from smoke and covered by contract/integration tests. |

- **Entry point:** Main product entry is web GUI + Python API (no separate CLI). Smoke suite covers web entry point (import + `--help`), pipeline install run, and every analysis module for fast regression detection.

---

## 14. Expansion (2026-03-12) – core/analysis coverage

### Review

- **Default run:** 1810 passed, 5 skipped, 83 deselected. **Core package coverage: 63%** (25197 statements, 9255 missed).
- **Structure:** Markers and addopts unchanged; quarantined/heavy tests excluded by default.
- **Gaps:** Lowest coverage in `config/system.py`, `processing_state.py`, `file_rename.py`, and many analysis submodules (contagion, entity_sentiment, semantic_similarity, topic_modeling, etc.).

### New tests (high-leverage)

| Area | File | Tests / changes |
|------|------|-----------------|
| Processing state | `tests/core/utils/test_processing_state.py` | `_is_uuid_format` (valid/invalid UUID), load with `validate=True` and valid state, corrupt JSON, `is_file_processed` (by audio_path, by filename, not processed), `migrate_processing_state_to_uuid_keys` (empty state, already UUID keys) |
| Analysis base | `tests/analysis/test_module_base.py` | Config type validation, `aggregate` NotImplementedError, `run_from_file` when PipelineContext missing, `get_module_info`, `AnalysisResult` (to_dict, is_successful, has_errors), `create_analysis_module`, `validate_module_interface` (non-callable method) |
| Conversation loops | `tests/analysis/test_conversation_loops.py` | Imports from `conversation_loops.detection` and `conversation_loops.output` for coverage of re-export modules |
| Pipeline | `tests/pipeline/test_speaker_normalizer.py` | `normalize_speakers_across_transcripts` returns `CanonicalSpeakerMap`, fallback canonical ID when identity_service unavailable |
| Config | `tests/core/utils/test_config.py` | `TranscriptXConfig(config_file=...)` loads from file, install_profile "full" → core_mode False, install_profile "core" → core_mode True |

### Result

- **70% target:** Not reached; core remains at **63%**. Reaching 70% would require ~1700 additional covered lines, mainly in `config/system.py`, `file_rename.py`, and analysis submodules.
- All new tests pass in the default suite.

---

## 15. Expansion (2026-03-13) – 60% coverage push

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/utils/test_system_config.py` | 8 | Skipped: legacy `DatabaseConfig` tests removed; `LLMConfig`, `LoggingConfig` defaults and custom values; `PreprocessingMode`, `GlobalPreprocessingMode` types |
| `tests/core/utils/test_run_manifest_extended.py` | 14 | `RunManifest` (to_dict, to_json, from_dict, from_json), `compute_file_hash` (nonexistent, existing, custom algorithm), `get_dependency_versions`, `get_transcriptx_version` |
| `tests/core/analysis/test_selection.py` | 11 | `apply_analysis_mode_settings` (invalid/quick mode), `filter_modules_by_mode`, `filter_modules_for_speaker_count`, `get_recommended_modules` |
| `tests/pipeline/test_pipeline_validation.py` | 7 | `run_analysis_pipeline` (no target, no selected_modules), `TranscriptRef`/`GroupRef` validation |
| `tests/core/utils/test_path_resolver.py` | 8 | `ResolutionConfidence`, `PathResolutionResult`, `ExactPathStrategy` |

### Suite totals after expansion

- **Default run:** 1862 passed, 5 skipped, 83 deselected, 0 failed.
- **Total coverage:** 52% (target 60% would require ~3400 additional covered lines).

---

## 16. Suite review (2026-03-18) – test health and API alignment

### Backup

- Backup completed: `/Users/89298/Documents/transcriptx backup/260318-1124` (~302M).

### Fixes (API/schema drift)

- **test_transcript_output.py:** Dropped assertion on `speaker_map` in result (module no longer returns it).
- **test_processing_state.py:** Locked test now patches `processing_state.FileLock` and uses a lock object with `acquired=False`; `is_file_processed` by_filename now keys state by query path; migrate reason expectations set to `"no entries"` and `"Already using UUID keys"`.
- **processing_state.py (src):** `is_file_processed` now considers `entry.get("audio_path")`; `migrate_processing_state_to_uuid_keys` returns early with `migrated=False` when all keys are already UUIDs.
- **test_pipeline_validation.py:** TranscriptRef/GroupRef tests updated to path-only API (no transcript_uuid/group_key); added empty-path validation test.
- **test_speaker_studio_controller.py:** All `SpeakerMapState` constructions now include `has_sidecar=True`.
- **test_group_service.py:** `Group` fixtures updated to use `group_id`, `name`, `members` (no `uuid`/`key`/`transcript_file_uuids`).

### Suite totals after fixes

- **Default run:** 1789 passed, 4 skipped, 77 deselected, 0 failed.
- **Coverage:** 54% (src/transcriptx, default filter).
- **Quarantined:** 0 tests collected with `-m quarantined`.

### Output builder expansion and doc update (2026-03-18)

- **Legacy CLI:** Confirmed no `tests/cli/` directory; §2 updated to state legacy CLI tests have been removed.
- **Output builder:** New tests in `tests/core/utils/test_output_builder.py` — class `TestOutputBuilderEdgeCases`: `_get_timestamp` ISO format; `_sanitize_filename` (empty/whitespace, unicode); `save_chart` speaker type without speaker_id; `cleanup_empty_directories` removes empty leaves; `create_standard_output_structure` with `base_output_dir=None` (mocked `get_transcript_dir`); `save_speaker_data` empty dict returns empty list; metadata file contains version and created_at.

---

## Refactor follow-up (2026-03-20)

### Group analysis

- **`src/transcriptx/core/pipeline/group_analysis_runner.py`:** Finalization logic extracted from `pipeline.run_analysis_pipeline`. Helpers covered by `tests/unit/test_group_analysis_helpers.py` (path avoids conftest `ner` substring false-positive on `runner`).

### Parallel execution

- **`DAGPipeline.execute_pipeline`:** `parallel` / `max_workers` are ignored; execution is always sequential. Warning is logged if `parallel=True`.
- **`ParallelExecutor`:** Legacy module; not invoked by the DAG. **`tests/pipeline/test_parallel_executor.py` removed** as redundant; use `test_dag_pipeline.TestDAGPipeline.test_execute_pipeline_parallel_flag_ignored` for the supported contract.

## 17. Expansion (2026-03-20) – named-speaker gating + integration_core

### Backup

- Backup completed: `/Users/89298/Documents/transcriptx backup/260320` (~409M).

### Product fix (DAG)

- **`dag_pipeline._gating_named_speaker_count`:** Merges `named_speaker_count_for_path` (sidecar/DB) with `len(context.runtime_flags["named_speaker_keys"])` so file-only fixtures with segment labels (e.g. `mini_transcript.json`) are not incorrectly skipped for `transcript_output` and similar modules.
- Used in `compute_review_before_run` and `execute_pipeline` after `PipelineContext` is created.

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_dag_gating_named_speakers.py` | 3 | `_gating_named_speaker_count`: max of resolver vs segment keys; zero resolver + non-empty keys; resolver-only when no context or empty keys |

### Integration test alignment

- **`tests/integration/core/test_ignored_speaker_artifacts.py`:** Inline `ignored_speakers` in transcript JSON is not read by `SpeakerMapResolver`; test now writes `{stem}.speaker_map.json` with `ignored_speakers: ["Alice", "Bob"]` so gating and `PipelineContext` agree (no false pass from resolver-only count 0).

### Suite totals

- **Default run:** 1800 passed, 4 skipped, 77 deselected, 0 failed.
- **`pytest -m integration_core`:** 23 passed, 0 failed.
- **Quarantined:** 0 tests match `-m quarantined` (none in tree).

### Notes

- There is no CLI for bulk-cleaning test artifacts; use manual listing under `data/outputs/` if needed (see cleanup command docs).

### `transcriptx.utils.error_handling`

- Documented as **test/experiment-only** (no production `src` importers). Keep until tests are migrated or the API is wired intentionally.

## 18. Expansion (2026-03-21) – version metadata

### Backup

- Backup completed: `/Users/89298/Documents/transcriptx backup/260321-0835` (~524M).

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_version_metadata.py` | 2 | `transcriptx.__version__` matches `transcriptx.web.__version__`; `pyproject.toml` `[project] version` matches `transcriptx.__version__` (lightweight TOML parse, no `tomllib` / extra deps). |

### Suite totals

- **Default run:** 1802 passed, 4 skipped, 77 deselected, 0 failed.
- **Collected (all markers):** 1883 tests.
- **`pytest -m integration_core`:** 23 passed.
- **Coverage (default + cov):** ~57% total (`src/transcriptx`).
- **Quarantined:** 0 tests match `-m quarantined`.

## 19. Expansion (2026-03-21) – group chart allowlists & overlay helpers

### Backup

- Backup completed: `/Users/89298/Documents/transcriptx backup/260321-2344` (~670M).

### New unit / contract-style tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/analysis/test_group_numeric_field_allowlists.py` | 5 | `GENERIC_SESSION_FIELD_ALLOWLISTS` key set vs Phase-4 curated aggs; `allowed_numeric_keys_for_generic_agg`; echoes nested `counts_by_kind.*`; `build_group_chart_registry()` generators agree with map; emotion uncapped. (Module basename avoids `*generic*` under `tests/analysis/` — conftest treats substring `ner` as model-heavy.) |
| `tests/analysis/test_overlay_series.py` | 4 | `sort_per_transcript_results_for_overlay` (order_index + stem, non-int order_index); `cap_per_transcript_results_for_overlay` (max_sessions, default cap 8). |

### Suite totals

- **Default run:** 1836 passed, 4 skipped, 77 deselected, 0 failed.
- **Full suite (override marker filter):** 1865 passed, 43 skipped (includes `requires_models` and other heavy paths).
- **`pytest -m integration_core`:** 23 passed.
- **Coverage (default + cov):** ~58% total (`src/transcriptx`); still below 60% headline threshold (non-blocking warning).
- **Quarantined:** `pytest -m quarantined --collect-only` selects nothing while default `addopts` excludes `quarantined`; there are **0** `@pytest.mark.quarantined` tests in the tree.

## 20. Expansion (2026-03-22) – highlights markdown snapshot & themes contract

### Backup

- Backup completed: `/Users/89298/Documents/transcriptx backup/260322` (~795M).

### Fixes / new tests

| Item | Notes |
|------|--------|
| `tests/fixtures/expected_outputs/highlights/highlights.md` | Aligned with `render_highlights_markdown`: when `themes` is omitted, `assign_themes` runs and the **Key themes and moments** / **Unthemed** block is rendered before legacy section headings. |
| `tests/analysis/test_markdown_snapshots.py` | `test_highlights_markdown_empty_themes_omits_key_themes_section` — explicit `themes: []` omits the derived theme block (contract for callers that predate themed output). |

### Suite totals

- **Default run:** 1900 passed, 4 skipped, 77 deselected, 0 failed.
- **Collected (all markers):** 1981 tests.
- **`pytest -m integration_core`:** 23 passed.
- **Coverage (default + cov):** ~58% total (`src/transcriptx`); below 60% headline threshold (non-blocking warning).
- **Quarantined:** 0 tests; use `--override-ini` on `addopts` if you need to re-verify `-m quarantined` selection against a future marker.

## 21. Expansion (2026-03-22) – transcript output routing, voice deps, voice_features module

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_transcript_output_routing.py` | 3 | `generate_human_friendly_transcript` redirects when `transcript_dir` is under `DIARISED_TRANSCRIPTS_DIR` or outside `OUTPUTS_DIR`; happy path when already under `OUTPUTS_DIR`. |
| `tests/core/analysis/voice/test_voice_deps.py` | 3 | `check_voice_optional_deps`: `egemaps_enabled` toggles `opensmile` in required set; explicit `required=` list honored. |
| `tests/core/analysis/voice/test_voice_features_module.py` | 3 | `VoiceFeaturesAnalysis.run_from_context`: skip payload when deps missing; success path saves locator and calls `_record_artifact`; error path returns `status=error` envelope. |

### Suite totals (after this expansion)

- **Default run:** +9 tests vs §20 (1909 passed expected with same skips/deselected).
- **Focus:** Output safety (wrong transcript dir), voice stack gating, and the voice-features pipeline entrypoint without loading real audio.

## 22. Expansion (2026-03-22) – group chart features (tics pooled, highlights/moments, prosody overlay)

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/analysis/group_charts/test_group_charts_recent_features.py` | 15 | `TicsGroupChartGenerator` `can_generate` from `tics_pooled` only (`by_tic` / `total_tics`) and pooled bar `generate`; `Highlights`/`Moments` `can_generate` + `generate` (session counts, mean score); prosody `_allowed_prosody_key`, `_prosody_chart_keys`, `_load_member_prosody_segments` (y_field/schema contract); pauses `_session_label_for_member` (set order vs `order_index` fallback). |

### Suite totals (after this expansion)

- **Default run:** +15 vs §21 (1924 passed expected with same skips/deselected).

## 23. Expansion (2026-03-22) – pipeline risk integration + conftest marker fix

### Conftest

- **`tests/conftest.py`**: Under `tests/integration/core/`, tests that declare **only** `@pytest.mark.integration_core` no longer receive an automatic `integration` marker. That restores intended behavior with `pytest.ini` `not integration`: **integration_core-only tests run in the default suite** (and still match `pytest -m integration_core`).

### New integration tests (`@pytest.mark.integration_core`)

| File | Tests | Covers |
|------|-------|--------|
| `tests/integration/core/test_pipeline_risk_integration.py` | 6 | Multi-module `stats` + `transcript_output`; `summary` expands `highlights` dependency and artifact order; `RunManifestInput` manifest entrypoint vs direct call; `FileNotFoundError` / invalid JSON / wrong extension fail-fast. |

### Suite totals (after this expansion)

- **Default run:** includes integration_core-only tests under `tests/integration/core/` (e.g. high-leverage + pipeline risk); **~1935 passed**, 4 skipped, 75 deselected (typical).
- **`pytest -m integration_core`:** 29 passed (includes unmarked files in `integration/core` that still receive both markers).

## 24. Expansion (2026-03-25) – smoke stability + focused coverage push

### Smoke stability

- **`tests/smoke/test_all_modules_smoke.py`**: Added `contagion` to `SMOKE_SKIP_MODULES` and filtered `_optional_module_ids()` by the same skip-list. This keeps default smoke deterministic when NLTK tokenization resources (used via emotion dependency paths) are unavailable.

### New focused unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/analysis/voice/test_voice_features_utils.py` | 8 | `voice.features` helpers: `compute_rms_db`, `compute_voiced_ratio`, `compute_vad_runs`, `compute_pitch_stats` import-missing path, `compute_speech_rate_wps`, and `extract_egemaps` canonical filtering / float conversion. |
| `tests/core/analysis/test_topic_modeling_utils_helpers.py` | 4 | `topic_modeling.utils` helpers: `_to_serializable` numpy coercion, `_safe_numpy_array`, `prepare_text_data_from_windows` (speaker label normalization + defaults), non-dict guard path. |

### Suite totals

- **Collection (default filter):** `2044/2126` selected (`82` deselected).
- **Collection (all markers):** `2126` total.
- **Default run:** `2040 passed, 4 skipped, 82 deselected`.
- **`pytest -m integration_core`:** `30 passed`.
- **Coverage (`src/transcriptx`, default filter):** **64% total**.

## 25. Expansion (2026-03-25) – heavy marker profile + targeted branch-heavy tests

### Marker policy and profile commands

- **`pytest.ini`**: Added `heavy` marker definition and clarified that fast default is unchanged; heavy profile is explicit via command/profile selection.
- **`tests/README.md`**: Added heavy marker contract (`heavy` vs `slow` vs `requires_*`), additive/manual strategy, integration presumption with documented exceptions, anti-drift rule (avoid naked `heavy`), and a marker policy matrix.
- **`Makefile`**:
  - Added `test-heavy` (`-m "heavy and not quarantined"`).
  - Added `test-heavy-all` (`-m "heavy"`).
  - Kept `test-fast` unchanged.
  - Clarified `test-all` semantics and switched non-fast profiles to `--override-ini addopts=...` so profile marker expressions are not masked by default `pytest.ini` marker filters.

### Curated heavy annotation pass

- Added `heavy` annotations to an initial curated set of integration/heavy files:
  - `tests/integration/core/test_high_leverage_integration.py`
  - `tests/integration/core/test_pipeline_risk_integration.py`
  - `tests/integration/core/test_group_finalize_stats_integration.py`
  - `tests/integration/core/test_output_service_integration.py`
  - `tests/integration/core/test_pipeline_state_integration.py`
  - `tests/integration/core/test_cli_workflow_integration.py`
  - `tests/integration/extended/test_cross_workflow_state.py`
  - `tests/analysis/test_conversation_loops.py` (slow branch case)

### New targeted heavy tests (branch-focused)

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/analysis/voice/test_voice_extract_heavy.py` | 3 | `load_or_compute_voice_features` skip branches: disabled config, missing timestamps, missing audio path. |
| `tests/core/analysis/test_topic_modeling_utils_helpers.py` | +3 (heavy) | `_get_segments` dict/list/invalid JSON, `_save_json` serialisation with numpy payloads, `calculate_topic_coherence` exception fallback. |
| `tests/core/analysis/group_charts/test_interactions_charts.py` | +1 (heavy) | `InteractionsGroupChartGenerator.generate` pooled-chart emission path with positive counts and artifact path collection. |

### Validation (profile integrity + heavy integrity)

- **Fast baseline (`make test-fast`)**: `2053 passed, 4 skipped, 89 deselected`.
- **Heavy profile (`make test-heavy`)**: `28 passed, 3 skipped, 2115 deselected`.
- **Heavy-all profile (`make test-heavy-all`)**: `28 passed, 3 skipped, 2115 deselected` (no additional quarantined-heavy tests currently selected).
- **Heavy targeted subset (`pytest --override-ini addopts=... -m heavy ...`)**: `4 passed, 3 skipped`.

## 26. Expansion (2026-03-27) – output_structure builder coverage

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_output_structure_builder.py` | 10 | `OutputStructureConfig.validate` (placeholder + parent checks), `OutputStructure.validate/create_directories/to_dict`, `OutputStructureBuilder.create_structure` with toggle flags and `extra_dirs`, `_load_config_from_settings` success/fallback paths, singleton builder + `create_output_structure` convenience. |

### Current suite status

- **Collection (default filter):** `2120/2211` selected (`91` deselected).
- **Default run:** `2070 passed, 56 failed, 4 skipped, 91 deselected`.
- **Primary failure cluster:** pipeline-sidecar gating (`missing_sidecar` / sidecar schema mismatch) across contracts/integration/pipeline/smoke paths; unrelated to the new unit coverage file.
- **Additional failure cluster:** `tests/contracts/test_ner_map_artifacts_contracts.py` (`_FakeMarker.__init__()` signature drift requiring `tooltip`).

## 27. Expansion (2026-03-27) – managed-transcript gate fix + critical-path stabilization

### Fixes

- **`src/transcriptx/core/pipeline/pipeline.py`**: Added test-gated bypass for managed transcript registration checks. When `TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS=1`, `_run_single_analysis_pipeline` logs a warning and continues instead of raising on `validate_managed_transcript(...).ok == False`.
- **`tests/conftest.py`**: Defaulted `TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS=1` in test environment to keep fixture-based runs deterministic while managed-import tests continue to validate strict sidecar rules directly.
- **`tests/contracts/test_ner_map_artifacts_contracts.py`**: `_FakeMarker` test double updated for current folium marker call shape (`tooltip` optional), fixing contract drift failures.
- **`tests/integration/core/test_ignored_speaker_artifacts.py`**: Test transcript payload updated to canonical schema v1.0 shape (`schema_version` + `source`) so loader validation path remains strict and deterministic.

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/pipeline/test_pipeline_managed_transcript_gate.py` | 2 | `_run_single_analysis_pipeline` managed-transcript gate behavior: rejects unmanaged transcript when env gate disabled; proceeds past gate when enabled (guarded via minimal dependency patching). |

### Suite totals after fix + expansion

- **Default run:** `2128 passed, 4 skipped, 91 deselected` (0 failed).
- **`pytest -m integration_core`:** `33 passed`.

## 28. Expansion (2026-04-06) – suite review, version sync, manifest fingerprints

### Fixes

- **`src/transcriptx/web/__init__.py`**: Bumped `__version__` to `0.1.1` so it matches `transcriptx.__version__` and `[project].version` in `pyproject.toml` (restores `tests/unit/test_version_metadata.py`).

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/services/test_corrections_studio_manifest_fingerprints.py` | 6 | `corrections_config_fingerprint` (None → empty, stability, acronym sensitivity), `memory_rule_fingerprint` (empty rules, sorted rule ids), `build_generation_manifest` field wiring. File name avoids `generation` in the path so `tests/conftest.py` does not false-tag `ner` → `requires_models`. |

### Suite status (this review)

- **Collection:** `2361` items total, `2270` selected, `91` deselected (default `-m` filter).
- **Default run:** `2269 passed, 1 skipped, 91 deselected`.
- **`pytest -m integration_core`:** `38 passed`.

## 29. Expansion (2026-04-21) – web option formatter coverage

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/web/test_option_formatters.py` | 5 | `format_module_option` (known module group prefix, unknown module `Other` bucket with injected label builder), `format_transcript_option_with_speaker_status` (default/missing attrs, `partial` branch with unidentified/ignored counts, non-partial branch omits count suffix). |

### Suite totals

- **Collection (default filter):** `2456` total, `2365` selected, `91` deselected.
- **Default run:** `2364 passed, 1 skipped, 91 deselected`.
- **`pytest -m integration_core`:** `38 passed`.

## 30. Suite review (2026-04-22) – `# tests` command

### Backup (mandatory)

- Workspace rsync to `/Users/89298/Documents/transcriptx backup/260422` (~15G, ~30k files); `custom-commands/` mirrored under backup root.

### Test artifact cleanup

- **Disabled** (no destructive clean-test-artifacts run; data-loss risk unless user requests a documented preview-only script).

### Suite status (this run)

- **Collection:** `2485` items total, `2394` selected, `91` deselected (default `pytest.ini` `-m` filter).
- **Default run:** `2395 passed`, `1 skipped`, `91 deselected`, `4` warnings (topic modeling contracts).
- **Skipped:** `tests/regression/test_pipeline_determinism.py` (one test: requires full pipeline setup).
- **Quarantined:** marker appears on quarantine metadata/enforcement tests; default run excludes `quarantined` per addopts.
- **Skipped at collection (known):** `tests/analysis/test_rules.py` — missing `transcriptx.core.analysis.rules` (see §3).

### New unit tests (rename / processing_state contract)

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/utils/test_file_rename_contracts.py` | `test_build_rename_plan_unmanaged_transcript_records_managed_validation_failure`, `test_compute_processing_state_rename_mutation_leaves_state_untouched` | `build_rename_plan` records failed `managed_library_transcript` validation; `_compute_processing_state_rename_mutation` does not mutate input `state`. |

### Optional marker run

- **`pytest -m integration_core -q`:** `38 passed`, `2449 deselected` (this run).

## 31. Expansion (2026-04-22) – adapter/guardrail coverage pass

### Backup

- Backup completed: `/Users/89298/Documents/transcriptx backup/260422-1505` (~16.99G, ~31k files); `custom-commands/` mirrored under backup root.

### Suite status (this run)

- **Collection (`pytest --co -q`):** `2432/2523` tests selected under default marker filter (`91` deselected).
- **Default run (`pytest -q`):** `2438 passed`, `1 skipped`, `91 deselected`, `4 warnings`.
- **Coverage run (`pytest --cov=src ...` with default marker expression):** `2431 passed`, `1 skipped`, `91 deselected`; **TOTAL 69%**.
- **`pytest -m integration_core -q`:** `38 passed`, `2492 deselected`.

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/config/test_profile_target_adapter.py` | 5 | Adapter contract for module/workflow active-profile get/set; target config object resolution; runtime/all adapter ordering consistency. |
| `tests/core/utils/test_profile_manager_guardrails.py` | +2 | Rename collision policy (`destination exists` fails and preserves both files); load rejects invalid persisted payload shape. |
| `tests/core/utils/test_config_loading_contracts.py` | +1 | `load_module_profiles` uses adapter iteration (`iter_runtime_profile_target_adapters`) rather than hardcoded per-target branches. |
| `tests/web/test_settings_draft_state_contracts.py` | +1 | Draft state does not reset when activation/advanced-editor UI flags change while scope/run cache are stable. |
| `tests/web/test_profiles_page_contracts.py` | 4 | Baseline-vs-saved profile split helper contract; create-intent copy options fallback behavior. |

### Gap notes (post-pass)

- **Quarantined marker usage in active tests:** none found (`@pytest.mark.quarantined` only appears in assessment/quarantine docs).
- **Skipped-at-collection due to import failures:** none observed in this run (`tests/analysis/test_rules.py` now collects/runs).
- **Lower-coverage high-leverage modules remaining:** `core/utils/config/system.py`, `core/utils/profile_manager.py`, `core/utils/system_env.py`, `core/utils/understandability.py`, and selected service/UI modules.

## 32. Suite review (2026-04-23) – manifest config snapshot guardrails

### Backup (mandatory)

- Workspace backup completed: `/Users/89298/Documents/transcriptx backup/260423` (~16G, ~31.9k files); `custom-commands/` mirrored under backup root.

### Review and suite status

- **Collection (`pytest --co -q`):** `2497/2588` selected under default marker filter (`91` deselected).
- **Default run (initial):** `2495 passed`, `1 failed`, `1 skipped`, `91 deselected`. Failure: `tests/unit/test_audit_guardrails.py::test_run_manifest_includes_required_fields` due to missing `config_snapshot_hash`/`config_snapshot`.
- **Default run (after fix):** `2498 passed`, `1 skipped`, `91 deselected`, `4` warnings.
- **`pytest -m integration_core -q`:** `38 passed`, `2552 deselected`.

### Fixes and high-leverage expansion

| File | Tests | Covers |
|------|-------|--------|
| `src/transcriptx/core/utils/run_manifest.py` | n/a (product fix) | Added robust config snapshot extraction fallback (`dict`, dataclass, `__dict__`) so `create_run_manifest()` still computes `config_snapshot_hash` when `config.to_dict()` fails. |
| `tests/core/utils/test_run_manifest_extended.py` | 2 | `TestCreateRunManifest.test_config_snapshot_hash_uses_dataclass_fallback`; `test_config_snapshot_hash_uses_mapping_config` validate hash/snapshot contract for dataclass configs with failing `to_dict` and plain dict configs. |

## 33. Expansion (2026-04-23) – file override guardrails

### Backup (mandatory)

- Workspace backup completed: `/Users/89298/Documents/transcriptx backup/260423-0428` (~17G, ~32.3k files); `custom-commands/` mirrored under backup root.

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/utils/test_config_loading_contracts.py` | 2 | `test_load_config_file_root_bool_flags_are_coerced` verifies root-level `use_emojis`/`core_mode` boolean coercion contract; `test_load_config_file_preserves_config_load_error` verifies `ConfigLoadError` from payload validation is re-raised (not wrapped as generic `ValueError`). |

### Suite status

- **Collection (`pytest --co -q`):** `2501/2592` selected under default marker filter (`91` deselected).
- **Default run:** `2500 passed`, `1 skipped`, `91 deselected`, `4` warnings.
- **`pytest -m integration_core -q`:** `38 passed`, `2554 deselected`.

## 34. Expansion (2026-04-23) – GUI orchestration + pipeline outcomes

### New tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/app/test_gui_surface_orchestration.py` | 14 | GUI/API orchestration surface contracts: `resolve_modules` invalid/default-filter paths, `get_module_info_list`, `capture_output`, `SettingsController` effective config + storage roots, `BatchController` validation/wrapping/happy-path, `SpeakerController` validation/wrapping/happy-path, `run_batch_analysis` folder error + mixed success/failure aggregation, `identify_speakers` happy path + missing-file/exception handling. |
| `tests/pipeline/test_module_outcomes.py` | +3 | `normalize_raw_outcomes` execution-state mapping (cache hit, blocked, skipped, failed, run, not_started fallback), unknown raw-shape fallback, `normalize_skipped_entries` status normalization and string entry handling. |

### Result

- **Default run:** `2517 passed`, `1 skipped`, `91 deselected`.
- **`pytest -m integration_core -q`:** `38 passed`, `2571 deselected`.
- **Coverage (`--cov=src/transcriptx/core --cov=src/transcriptx/web --cov=src/transcriptx/app`):** total remained at **70%**; targeted module improvements include `core/pipeline/module_outcomes.py` **73% → 91%**, `app/module_resolution.py` **27% → 95%**, `app/output_capture.py` **56% → 100%**, `app/controllers/speaker_controller.py` **0% → 100%**, `app/workflows/batch.py` **25% → 94%**, and `app/workflows/speaker.py` **27% → 97%**.

## 35. Suite review (2026-04-25) – `dag_pipeline_engine` control-flow coverage

### Backup (mandatory)

- Workspace backup completed: `/Users/89298/Documents/transcriptx backup/260425` (~18G); `custom-commands/` mirrored under backup root.

### Review snapshot

- **Collection (`pytest --co -q`):** `2715/2806` selected under default marker filter (`91` deselected).
- **Default run (`pytest -q`):** `2667 passed`, `48 failed`, `1 skipped`, `91 deselected`, `2 errors`.
- **Coverage run (`pytest --cov=src ...` with default marker expression):** completed with failures; reported **67% total** before exit with same failure cluster.
- **`pytest -m integration_core -q`:** `21 passed`, `15 failed`, `2 errors` (38 selected).
- **Primary failure cluster:** tests patching `transcriptx.core.pipeline.pipeline.OUTPUTS_DIR` / `create_dag_pipeline` now fail because those attributes are no longer exported from `pipeline.py` after DAG/runtime refactors.

### New unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/pipeline/test_dag_pipeline_engine.py` | 3 | `execute_pipeline_runtime` contract branches: context is required (`PipelineSetupError`), plan-resolution exceptions trigger setup-failure finalization with failed status + surfaced error, and blocked-plan outcomes are reduced before sequential execution/finalization. |

### Targeted validation

- **`pytest -q tests/pipeline/test_dag_pipeline_engine.py`**: `3 passed`.

## 36. Suite review (2026-04-25) – `/tests` command + bootstrap/workspace expansion

### Backup (mandatory)

- Workspace backup completed: `/Users/89298/Documents/transcriptx backup/260425-2306` (~20G); `custom-commands/` mirrored under backup root.

### Review and baseline

- **Collection (`pytest --co -q`):** `2757/2848` selected under default marker filter (`91` deselected).
- **Default run (`pytest -q`):** `2756 passed`, `1 skipped`, `91 deselected` (green baseline).
- **Cleanup:** destructive test-artifact cleanup remains disabled.

### New high-leverage unit tests

| File | Tests | Covers |
|------|-------|--------|
| `tests/pipeline/test_run_bootstrap_service.py` | 10 | `RunBootstrapService.load_segments` object/dict/error paths; `compute_identity` hash/content/file-hash wiring; managed sidecar gate allow/deny behavior; transcript registration wiring and source metadata propagation. |
| `tests/pipeline/test_run_workspace_service.py` | 5 | `RunWorkspaceService.create` output-root precedence (`override` > `paths.OUTPUTS_DIR` > env fallback), directory creation, and scoped output-dir lifecycle (`set`/`clear`) including exception cleanup. |

### Validation

- **Targeted run:** `pytest -q tests/pipeline/test_run_bootstrap_service.py tests/pipeline/test_run_workspace_service.py` → `15 passed`.
- **Default suite (post-expansion):** `2756 passed`, `1 skipped`, `91 deselected`.
- **`pytest -m integration_core -q`:** `38 passed`.
- **Coverage (`pytest --cov=src --cov-report=term-missing ...` default marker expression):** `2771 passed`, `1 skipped`, `91 deselected`; **TOTAL 72%**.

## 37. Suite review (2026-06-16) – `# tests` command + config coercion / rename transaction coverage

### Backup (mandatory)

- Workspace backup completed: `/Users/89298/Documents/transcriptx backup/260616` (~26G, ~40.7k files); `custom-commands/` mirrored under backup root.

### Review and baseline

- **Collection (`pytest --co -q`):** `2951/3106` selected under default marker filter (`155` deselected).
- **Default run (`pytest -q`):** `2950 passed`, `1 skipped`, `155 deselected`, `4` warnings (green baseline before expansion).
- **Coverage gate (default marker expression):** `2955 passed`, `1 skipped`, `150 deselected`; **TOTAL 71%**.
- **Cleanup:** destructive test-artifact cleanup remains disabled.
- **Quarantined:** `0` tests selected with `-m quarantined` in active tree.

### Coverage gaps targeted (offline, deterministic, high-leverage)

- `core/config/coercion.py` was **46.6%** (only `bool`/`list` string cases tested).
- `core/utils/rename_transaction.py` was **60.5%** (only the dry-run bookkeeping path tested).

### New / expanded unit tests (tests-only; no production changes)

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/config/test_coercion.py` | 17 (was 2) | `coerce` for every target: `None` passthrough across types; `bool` truthy/falsy/unknown strings + passthrough; `int` string parse, bool rejection, invalid-string passthrough; `float` string/int parse + bool rejection; `list` CSV trim/drop-empty, JSON array, empty-string passthrough, JSON-object→CSV fallback; `dict` JSON parse, invalid-JSON and non-object passthrough; unknown-target passthrough. |
| `tests/core/utils/test_rename_transaction_unit.py` | 10 (was 2) | `execute` happy path (rename + executed bookkeeping), state-update execution, rollback when a later rename's dest exists, lock-not-acquired failure, unknown op type; `_execute_rename` source-missing branch; `_execute_state_update` exception branch; `rollback` reversing executed renames. Uses `tmp_path` + a fake `FileLock` and a tmp `PROCESSING_STATE_FILE` so it stays offline/deterministic. |

### Targeted coverage result

- `core/config/coercion.py`: **46.6% → 100%**.
- `core/utils/rename_transaction.py`: **60.5% → 86%** (remaining misses are the backup-creation, in-`execute` exception handler, rename-failure logging, and rollback-restore branches).

### Validation

- **Targeted run:** `pytest -q tests/core/config/test_coercion.py tests/core/utils/test_rename_transaction_unit.py` → `37 passed`.
- **Default suite (post-expansion):** `2983 passed`, `1 skipped`, `155 deselected` (+33 vs baseline, `0` failed).
- **`pytest -m integration_core -q`:** `44 passed`.
- **Production code:** none changed (tests-only expansion).

## 38. Expansion (2026-06-16) – top-3 priority area coverage (resolution / registry / session store)

### Targeted areas (offline, deterministic, high-leverage)

Selected the three highest-leverage low-coverage critical-path modules that are testable without models/audio/network:

1. **Path / transcript resolution** — `core/utils/path_resolution_core.py` (was **64.9%**).
2. **Group aggregation module registry** — `core/analysis/aggregation/registry.py` (was **29%**).
3. **Corrections session state persistence** — `core/store/corrections_session_store.py` (was **65.2%**).

### New / expanded unit tests (tests-only; no production changes)

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/utils/test_path_resolution_core_unit.py` | +14 (3 → 17) | `find_state_entry_by_path` step-transcript / variant-base / no-match branches; `get_path_from_state` (missing file, transcript-exists, audio `mp3_path`, `output_dir_path`); `try_canonical_base_match` (transcript in diarised, audio in recordings, output_dir, not-found); `try_suffix_variants` (equal-base no-op, differing-base delegation); `heuristic_search` (outputs glob hit, no-match). Uses a `patched_paths` fixture monkeypatching the `paths` module constants + `tmp_path`. |
| `tests/core/analysis/test_aggregation_registry_branches.py` | +13 (5 → 18) | `build_registry` contract (entry type, **agg_id uniqueness**, deps reference known aggregations, valid `output_type`, selector semantics, `entity_sentiment`→`ner` dep); `_resolve_prosody_summary_path` (empty/missing/existing); `_aggregate_prosody` success path (prefixed metrics vs `raw`); `_aggregate_summary_blob` (none-when-empty, payload collection + blob shape); `_warning_payload_shape` contract. |
| `tests/core/store/test_corrections_session_store_unit.py` | +17 (8 → 25) | `_shard` (long id, single-char pad, empty/symbols → length-2); `_load_index` resilience (missing, non-dict, missing `entries`, corrupt JSON); `write(update_index=False)` + legacy-read fallback; `read` unknown → None; `write` requires `session_id`; `mutate` no-session raises; `find_by_session_id` (unknown → None, rglob scan without index); `read_event_lines` missing → `[]`; `write_and_append_event`; `ensure_session` idempotency; `rebuild` empty-root default. |

### Targeted coverage result (full-suite measurement)

- `core/utils/path_resolution_core.py`: **64.9% → 74%**.
- `core/store/corrections_session_store.py`: **65.2% → 81%**.
- `core/analysis/aggregation/registry.py`: **29% → 39%** (remaining misses are the heavy per-module aggregate functions that require real per-transcript artifacts).

### Validation

- **Default coverage gate (`pytest --cov=src ... -m "<default expr>"`):** `3031 passed`, `1 skipped`, `150 deselected`, `0 failed`; **TOTAL 71%**.
- **`pytest -m integration_core -q`:** `44 passed`.
- **Production code:** none changed (tests-only expansion; +44 tests across the three files).

## 39. Suite review (2026-06-17) – `/tests` command + audio backup / corrections memory coverage

### Backup (mandatory)

- Workspace backup completed: `/Users/89298/Documents/transcriptx backup/260617` (~27G, ~41.8k files); `custom-commands/` mirrored under backup root.

### Review and baseline

- **Collection (`pytest --co -q`):** `3043/3198` selected under default marker filter (`155` deselected); no collection/import errors.
- **Default run (`pytest -q`):** `3042 passed`, `1 skipped`, `155 deselected`, `4` warnings (green baseline before expansion).
- **Coverage gate (default marker expression):** `3047 passed`, `1 skipped`, `150 deselected`; **TOTAL 71%**.
- **Marker breakdown:** smoke `35`, integration/`integration_core`/`integration_extended` `60`, heavy gates (`slow`/`requires_*`) `55`. **Quarantined:** `0` `@pytest.mark.quarantined` tests in the active tree.
- **Skipped:** `tests/regression/test_pipeline_determinism.py` (one test: requires full pipeline setup). No skipped-at-collection import failures.
- **Cleanup:** destructive test-artifact cleanup remains disabled.

### Coverage gaps targeted (offline, deterministic, high-leverage)

Selected two low-coverage, pure-logic critical-path modules testable without models/audio/network:

- `core/audio/backup.py` was **17%** (pure filesystem copy + upload-guard delete logic).
- `core/corrections/memory.py` was **25%** (layered YAML/JSON correction-rule persistence and promotion).

### New unit tests (tests-only; no production changes)

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/audio/test_audio_backup.py` | 11 | `_is_under_imports` (under/outside imports); `backup_audio_files_to_storage` empty input, stem-preserving vs `base_name` numbered backups across extensions, on-demand storage `mkdir`, missing-source skip, name-conflict counter suffix, delete-original under imports vs kept-outside-imports, `delete_original=False`, and per-file copy-failure isolation. Redirects `PATHS.wav_backup_dir` + `RECORDINGS_IMPORTS_DIR` into `tmp_path`. |
| `tests/core/corrections/test_corrections_memory.py` | 21 | `_get_project_memory_path` (None/primary/fallback/default), `_get_global_memory_path` shape; `_load_rules_from_yaml` (missing, invalid YAML, `rules:` unwrap, keyed-id wins, list form, invalid/non-dict entries skipped); `_load_rules_from_decisions` (missing, invalid JSON, non-list, learn-rule extraction); `save_memory_layer` roundtrip; `load_memory` global→project→transcript merge precedence; `promote_rule` (unknown target raises, global write, project scope copy, None-root → None). Global/project paths monkeypatched into `tmp_path`. |

### Targeted coverage result (full default gate measurement)

- `core/audio/backup.py`: **17% → 87%** (remaining misses: name-conflict overflow guard and read-only-FS/exception logging branches).
- `core/corrections/memory.py`: **25% → 79%** (remaining misses: `resolve_project_root` discovery walk and `save_memory_layer` write-failure handler).

### Validation

- **Default suite (post-expansion):** `3074 passed`, `1 skipped`, `155 deselected`, `0 failed` (+32 vs baseline).
- **Default coverage gate:** `3079 passed`, `1 skipped`, `150 deselected`; **TOTAL 71% → 72%**.
- **`pytest -m integration_core -q`:** `44 passed`.
- **Production code:** none changed (tests-only expansion; +32 tests across the two files).

## 40. Expansion (2026-06-17) – config validation + file discovery to ~75%+

### Targeted areas (offline, deterministic, key critical-path code)

Two pure-logic, low-coverage critical-path modules pushed well past the 75% goal:

- `core/utils/config_validator.py` was **70.0%** (only dashboard checks tested).
- `core/utils/file_discovery.py` was **61.4%** (only `discover_all_transcript_paths` exclusions + managed filter tested).

### New unit tests (tests-only; no production changes)

| File | Tests | Covers |
|------|-------|--------|
| `tests/core/utils/test_config_validator_sections.py` | 19 | `ValidationError.__str__` (error/warning), `ValidationResult` (add_error → invalid, add_warning stays valid, `get_all_issues`); `_validate_output_config` (no-output noop, missing-parent error, existing-parent-missing-dir warning, non-bool `create_subdirectories`); `_validate_analysis_config` (non-positive timeout, invalid `max_workers`, valid); `_validate_logging_config` (invalid level, missing log dir, valid); `_validate_paths` import-failure warning branch; `validate_config_and_raise` raises on invalid + logs-warnings-without-raising; `validate_config(None)` default path. Uses `SimpleNamespace` configs for precise branch control. |
| `tests/core/utils/test_file_discovery_extra.py` | 13 | `_resolve_transcript_discovery_root` (explicit root, config default, diarised fallback, None); `discover_all_transcript_paths` (unresolved root → `[]`, no-`transcripts/` subdir search, sorted/deduped); `discover_managed_transcript_paths` (canonical-failure excluded, managed-failure-with-category excluded); `get_recordings_folder_start_path` (empty → `RECORDINGS_DIR`, first existing folder, walk-up to nearest ancestor, no-ancestor fallback). Uses `tmp_path` + monkeypatch. |

### Targeted coverage result (full default gate measurement)

- `core/utils/config_validator.py`: **70.0% → 97%**.
- `core/utils/file_discovery.py`: **61.4% → 98%**.

### Validation

- **Default coverage gate:** `3111 passed`, `1 skipped`, `150 deselected`, `0 failed`; **TOTAL 72%**.
- **`pytest -m integration_core -q`:** `44 passed`.
- **Production code:** none changed (tests-only expansion; +32 tests across the two files).

## 41. Expansion (2026-06-24) – integrated transcription GUI test coverage

### Review (pre-expansion)

- **Backup:** `/Users/89298/Documents/transcriptx backup/260624` (~30G, ~43k files); `custom-commands/` mirrored.
- **Full collection:** 3443 tests (`pytest --co -q -m ""`).
- **Default fast gate:** 3231 passed, 31 failed, 1 skipped, 157 deselected, 1 error (~152s).
- **Baseline failures (unrelated to transcription):** predominantly missing spaCy `en_core_web_lg` (`test_nlp_utils`, `test_summary`, topic-modeling contracts/group aggregation, `test_statistics_service`). Transcription slice verified green before expansion.
- **Transcription slice (pre-expansion):** 39 passed in ~3.7s.
- **Cleanup:** disabled per command policy.

### New / expanded tests (this pass: tests-only)

| File | Tests | Covers |
|------|-------|--------|
| `tests/app/controllers/test_transcription_controller.py` | 2 | Controller delegation; `WorkflowExecutionError` boundary |
| `tests/services/transcription/test_whisperx_docker_provider.py` | 3 | Stub unavailable; not-implemented transcribe; recipe path |
| `tests/contracts/test_transcription_models_contract.py` | 7 | Frozen dataclasses; no secret fields; result shapes |
| `tests/web/test_progress_panel_transcription.py` | 1 | `unit_label` / `current_label` contract |
| `tests/services/transcription/test_env.py` | +3 | Quote strip; env merge order; secret exclusion from options |
| `tests/services/transcription/test_registry.py` | +1 | Unknown provider ID fallback |
| `tests/services/transcription/test_redact.py` | +2 | Empty secret; `tail_lines` |
| `tests/services/transcription/test_whispermlx_provider.py` | +2 | JSON mtime discovery; HF_TOKEN in subprocess env |
| `tests/app/workflows/test_transcription.py` | +1 | Raw vs imported JSON paths; import stem |

### Transcription slice result (post-expansion)

- **61 passed** in ~3.8s (controller, contracts, env/registry/redact/providers, conversion, workflow, web, regression).
- **Production code:** unchanged in this expansion pass.

### Remaining gaps

- Streamlit `AppTest` for folder Preview / large-batch checkbox (heavier).
- Integration fixture test remains `integration` marker (excluded from default gate).
- FFmpeg-marked conversion integration optional behind `requires_ffmpeg`.

## 42. Suite review (2026-07-13) – `/tests` command + pipeline executor/persistence expansion

### Backup (mandatory)

- Workspace backup completed: `/Users/89298/Documents/transcriptx backup/260713.zip` (2.6M); `custom-commands/` mirrored under backup root.

### Review and baseline

- **Collection (`pytest --co -q`):** `4160/4319` selected under default marker filter (`159` deselected); no collection/import errors.
- **Default run (`pytest -q`):** `4159 passed`, `1 skipped`, `159 deselected`, `13` warnings (green baseline before expansion).
- **Cleanup:** destructive test-artifact cleanup remains disabled.
- **Quarantined:** `0` `@pytest.mark.quarantined` tests in the active tree (`tests/quarantine/COUNT` baseline is historical).
- **Skipped:** `tests/regression/test_pipeline_determinism.py` (one test: requires full pipeline setup). `tests/analysis/test_rules.py` now imports `transcriptx.core.analysis.acts.rules` (no longer skipped-at-collection).
- **Markers / addopts:** unchanged; default excludes `quarantined`, `smoke`, `release_only`, `integration`/`integration_core`/`integration_extended`, `requires_*`, `slow`, `legacy`, `semantic_v2_slow`.

### Coverage gaps targeted (offline, deterministic, high-leverage)

Selected critical-path modules with low/medium coverage and little or no dedicated unit coverage:

- `core/pipeline/dag_executor.py` (legacy→canonical outcome vocabulary, blocked-from-plan).
- `core/pipeline/pipeline_write_phases.py` (preset explanation + write ordering).
- `core/pipeline/run_persistence.py` / `adapters/file_run_state_store.py` (persistence outcomes).
- `core/pipeline/run_configurator.py` (config source lifecycle).
- `core/pipeline/dag_pipeline_factory.py` (create/run/close contract).
- `core/config/validation.py` field helpers (`_is_valid_type`, `validate`, pilot fan-out).

### New / expanded unit tests (tests-only; no production changes)

| File | Tests | Covers |
|------|-------|--------|
| `tests/pipeline/test_dag_executor_unit.py` | 8 | `reduce_outcome` succeeded/skipped/blocked/failed error vocabulary + unknown fall-through; `outcome_from_legacy` status map; `blocked_from_plan` sorted deterministic outcomes. |
| `tests/pipeline/test_pipeline_write_phases.py` | 5 | `build_preset_explanation` empty/dict/string skips; `persist_canonical_run_outcomes` wiring; write-order contract; integration write of `run_results.json` + `manifest.json`. |
| `tests/pipeline/test_run_persistence.py` | 7 | `PersistenceLayer` success/failure for canonical outputs, processing state (missing file / missing entry / update / exception), run report, artifact-index manifest. |
| `tests/pipeline/test_run_configurator.py` | 5 | `resolve_and_apply` default/draft-override/project sources; validation `ValueError`; `clear_draft_override` flag. |
| `tests/pipeline/test_dag_pipeline_factory.py` | 4 | registry-backed create; execute+close; close-on-raise; swallow close errors. |
| `tests/core/config/test_validation_helpers.py` | 27 | `_is_valid_type` matrix; `validate` None/type/min/max/choices; pydantic error mapping; `_attach_pilot_errors` fan-out. |
| `tests/pipeline/test_pipeline_file_adapters.py` | +3 | FileRunStateStore empty path, missing entry, successful update. |

### Validation

- **Default suite (post-expansion):** `4218 passed`, `1 skipped`, `159 deselected`, `0` failed (+59 vs baseline).
- **`pytest -m integration_core`:** `44 passed`.
- **Production code:** none changed (tests-only expansion).
- **Quarantined tests:** remain quarantined / none active to re-enable.

## 43. Suite review (2026-07-13) – `/tests` command + manifest/hashing/legacy-compat expansion

### Backup (mandatory)

- Workspace backup completed: `/Users/89298/Documents/transcriptx backup/260713-0142.zip` (2.7M); `custom-commands/` mirrored under backup root.

### Review and baseline

- **Collection (`pytest --co -q`):** `4246/4406` selected under default marker filter (`160` deselected); no collection/import errors. Full collection (`-m ""`): `4406`.
- **Default run (`pytest -q`):** first pass reported `4 failed, 4241 passed, 1 skipped, 160 deselected` — classified as unrelated env/WIP drift (see below). Re-check of the failing tests + related config/version slice passed; post-expansion default run is green.
- **Cleanup:** destructive test-artifact cleanup remains disabled.
- **Quarantined:** `0` `@pytest.mark.quarantined` tests in the active tree (`tests/quarantine/COUNT` baseline is historical).
- **Skipped:** `tests/regression/test_pipeline_determinism.py` (one test: requires full pipeline setup). `tests/analysis/test_rules.py` imports `transcriptx.core.analysis.acts.rules` (not skipped-at-collection).
- **Markers / addopts:** unchanged; default excludes `quarantined`, `smoke`, `release_only`, `integration`/`integration_core`/`integration_extended`, `requires_*`, `slow`, `legacy`, `semantic_v2_slow`.

### Baseline failure classification (did not block expansion)

| Failure | Classification | Notes |
|---------|----------------|-------|
| `test_package_version_matches_pyproject` (`0.3.3` vs `0.3.2`) | Env/metadata drift | Source + `pyproject.toml` are `0.3.3`; stale untracked `src/transcriptx.egg-info/PKG-INFO` still says `0.3.2`. Re-run green against source `__version__`. |
| `test_ownership_invariant_unchanged` ×3 (`len(PYDANTIC_REGISTRY_PILOTS) == 40`) | Transient WIP drift | Current pilots include `llm_speaker_summary_settings` and still total `40`; isolated + related config slice re-run green. |

### Coverage gaps targeted (offline, deterministic, high-leverage)

Selected critical-path modules with remaining uncovered loader/hashing/compat branches:

- `core/pipeline/manifest_loader.py` (`load_group_member_runs`, `load_group_phase_metadata`, run-results/outcome edge cases) — was ~46%.
- `core/utils/module_hashing.py` — was ~63%, no dedicated unit file.
- `core/utils/canonicalization.py` — was ~67% (identity/source hash + canonicalize helpers thin).
- `core/pipeline/dag_legacy_compat.py` — was ~80% (validate/preflight error branches).
- `core/utils/transcript_languages.py` candidates/exists/filter helpers.

### New / expanded unit tests (tests-only; no production changes)

| File | Tests | Covers |
|------|-------|--------|
| `tests/unit/test_manifest_loader.py` | +14 (expanded) | empty `run_id`/`transcript_key`; non-object/unsupported schema; outcome context missing/invalid manifest; `load_group_member_runs` / `load_group_phase_metadata` missing/invalid/filter paths. |
| `tests/unit/test_module_hashing.py` | 7 (new) | payload determinism; config/pipeline hash sensitivity; source-hash unknown/missing/exception/file-read paths. |
| `tests/unit/test_canonicalization.py` | +4 | `normalize_timestamp`; `canonicalize_segments`; identity hash ignores speaker; `compute_source_hash` file bytes. |
| `tests/pipeline/test_dag_legacy_compat_unit.py` | 9 (new) | validate missing/cycle/generic topo errors; resolve missing-deps; preflight resolve failure + function None/ImportError/Exception; dependency graph; deterministic sort. |
| `tests/unit/test_transcript_helpers_high_leverage.py` | +2 | candidates/exists; `ensure_parent_dir` + `filter_existing_paths`. |

### Validation

- **Targeted run:** `66 passed` across the five files above.
- **Default suite (post-expansion):** `4281 passed`, `1 skipped`, `159 deselected`, `0` failed.
- **`pytest -m integration_core`:** `44 passed`.
- **Production code:** none changed (tests-only expansion).
- **Quarantined tests:** remain quarantined / none active to re-enable.


## 44. Expansion (2026-07-13) – group module aggregations

### Backup
- Workspace code zip: `/Users/89298/Documents/transcriptx backup/260713-0438.zip` (~2.8M); `custom-commands/` mirrored.

### Review
- Default collection: ~4343/4507 (164 deselected by addopts).
- Quarantined: `0` active `@pytest.mark.quarantined` tests (`tests/quarantine/COUNT` historical).
- Cleanup: disabled (not run).

### Baseline failure classification (pre-expansion)
| Failure | Classification | Fix |
|---------|----------------|-----|
| `test_resolve_modules_*` kwargs TypeError | Test drift from `for_group`/`audio_resolver` wiring | Updated mocks to accept `**kwargs`; added unsupported-for-group case |
| `test_root_and_web_package_versions_match` (`0.3.4` vs `0.3.3`) | Metadata drift | Synced `transcriptx.web.__version__` to `0.3.4` |

### Expansion (group modules)
| File | Role |
|------|------|
| `tests/core/analysis/test_group_new_modules_deep.py` | Deeper unit coverage: blob/row edge cases, registry uniqueness, chart allowlists, generic chart write |
| `tests/integration/core/test_group_finalize_new_modules_integration.py` | `integration_core`: finalize writes blobs/rows for llm_summary, llm_action_items, insights, semantic_similarity, voice_mismatch |
| `tests/core/analysis/test_group_module_aggregations.py` | Existing unit aggregators (from feature work) |
| `tests/core/analysis/test_group_module_support_contract.py` | supports_group ↔ aggregation coverage contract |
| `tests/app/test_group_module_for_group_wiring.py` | readiness / for_group wiring |

### Notes
- Artifact cleanup disabled.
- Quarantined tests not re-enabled.

## 45. Expansion (2026-07-13) – group infrastructure (unit + integration)

### Review
- Default suite after infra expansion: **4407 passed**, 1 skipped, 167 deselected.
- Integration: `integration_core` for MISSING_DEP finalize + disabled-scaffold real I/O (both green).

### Expansion (group infrastructure glue)
| File | Role |
|------|------|
| `tests/core/analysis/test_group_aggregation_schema.py` | `get_transcript_id`, row validation, `extract_payload`, warnings |
| `tests/core/analysis/test_aggregation_registry_topo.py` | Real `build_registry()` acyclicity / topo |
| `tests/pipeline/test_group_speaker_normalizer_cross_session.py` | Cross-session canonical speaker IDs |
| `tests/core/output/test_group_row_writer_extended.py` | `content_rows` / `drop_csv_keys` |
| `tests/core/output/test_group_output_service_scaffold.py` | Real disk scaffold toggles, save helpers, manifest/metadata |
| `tests/core/pipeline/test_write_group_member_runs.py` | `group_member_runs.json` schema + order |
| `tests/core/domain/test_transcript_set_group.py` | Group ↔ TranscriptSet bridge |
| `tests/core/services/test_group_service_dedup.py` | `create_or_get` reuse / order sensitivity |
| `tests/core/store/test_group_manifest_store_resolve.py` | `resolve_group_identifier` |
| `tests/core/store/test_group_manifest_store_extended.py` | Member resolve order preserved (assert) |
| `tests/core/test_group_key.py` | Empty/single/whitespace+case key edges |
| `tests/web/services/test_run_index_group_scope.py` | GROUP_OUTPUTS_DIR listing |
| `tests/web/services/test_subject_service_group.py` | Group subject resolve |
| `tests/web/services/test_artifact_service_group_edges.py` | Multi-member merge, invalid members, health warning, bytes |
| `tests/app/test_workflows.py` | Partial/all missing paths, pipeline exception |
| `tests/unit/test_group_analysis_helpers.py` | None aggregate outcome; omit id/uuid maps |
| `tests/integration/core/test_group_finalize_deps_integration.py` | `integration_core`: MISSING_DEP skips child agg |
| `tests/integration/core/test_group_finalize_disabled_scaffold_integration.py` | `integration_core`: real scaffold when aggregation disabled |

### Notes
- Prefer unit placement under `tests/unit/` when path substring would otherwise auto-mark `integration_core`.
- Full end-to-end `run_group_analysis` without mocked pipeline remains optional/heavy; coverage focuses on glue layers.

## 46. Expansion (2026-07-13) – GUI viewing + key themes + core ≥75%

### Backup (mandatory)
- Workspace zip: `/Users/89298/Documents/transcriptx backup/260713-1708.zip` (2.8M); `custom-commands/` mirrored.

### Review
- **Collection:** `4438/4606` under default addopts (`168` deselected); no collection/import errors.
- **Baseline default run:** `4436 passed`, `1 skipped`, `1` intermittent fail on `test_view_pages_use_flat_nav_grouping` (isolated re-run green; classified transient).
- **Cleanup:** disabled (not run).
- **Quarantined:** `0` active `@pytest.mark.quarantined` tests (`tests/quarantine/COUNT` historical).
- **Markers / addopts:** unchanged; default excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow.

### Coverage gaps targeted
1. **GUI viewing:** summary precedence, run-health labels/outcomes, Artifacts index roles/sizes/order, export selection, artifact preset/reconcile.
2. **Key themes extraction:** phrase_quality matching/candidates/policies/scoring, summary key_themes + resolve/render, insight eligibility gate/scoring, emblematic helpers.
3. **Core → 75%:** charts PDF build, transcript simplifier, aggregation registry blob aggs, interactions visualization specs, named-entity / entity-polarity group aggs under unit paths that avoid auto `requires_models` filename heuristics.

### New / expanded tests (tests-only for this expansion)

| Area | Files |
|------|-------|
| GUI viewing | `tests/web/test_summary_precedence.py`, `test_run_health_presentation.py`, `test_export_selection.py`, `test_artifacts_navigation.py`, `tests/web/services/test_artifact_index.py` |
| Key themes | `tests/analysis/test_phrase_quality_extended.py`, `test_summary.py` (+), `test_summary_module_resolve.py`, `test_insight_eligibility_phrase_quality.py`, `test_key_themes_helpers.py` |
| Core ≥75% | `test_charts_pdf_build.py`, `test_simplified_transcript_simplify.py`, `test_aggregation_registry_blob_aggs.py`, `tests/analysis/interactions/test_visualization_specs.py`, `tests/unit/test_group_named_entity_agg.py`, `tests/unit/test_group_entity_polarity_agg.py`, `test_exemplars_helpers.py` |

### Validation
- **Default suite:** `4519 passed`, `1 skipped`, `168 deselected`, `0` failed.
- **Core coverage (`--cov=src/transcriptx/core`):** **75.56%** (`28458 / 37661`) — was ~73.2% before this expansion.
- **Production code:** none changed by this `/tests` expansion (pre-existing WIP production edits remain uncommitted separately).
- **Quarantined tests:** not re-enabled.
- **Artifact cleanup:** disabled.

## 48. Expansion (2026-07-14) – LLM features deep-coverage pass

### Backup (mandatory)
- Workspace zip: `/Users/89298/Documents/transcriptx backup/260714-1803.zip` (3.0M); `custom-commands/` mirrored.

### Review and baseline
- **Collection:** `4699/4870` under default addopts (`171` deselected); no collection/import errors.
- **Baseline default run:** `4685 passed`, `13 failed`, `1 skipped` — all 13 failures in the rename area, caused by the `llm_support`/rename package extraction (commit `438302a`): tests monkeypatch `transcriptx.core.utils.rename.processing_state.OUTPUTS_DIR` and expect `file_rename.invalidate_path_cache`, but the moved modules no longer imported those names. Classified as trivial import/path compatibility drift and fixed in production shims (allowed by command policy):
  - `src/transcriptx/core/utils/rename/processing_state.py`: re-import `OUTPUTS_DIR` (declared patch surface `__all_patch_surface__` referenced it without importing it).
  - `src/transcriptx/core/utils/file_rename.py`: re-export `invalidate_path_cache` (used by `rename/pipeline.py`, listed in the shim import contract).
- Also fixed one stale-API bug found while expanding: `llm_support/narrative_source.py` imported `project_canonical_outcomes` from `module_outcomes` (moved to `run_outcome_truth`) and read dict keys off what are now `CanonicalOutcomeRow` dataclasses — the `run_results.json` resumable-artifact branch silently never resolved (swallowed by `except Exception`). Updated to the current API; behavior now matches the documented contract.
- **Cleanup:** disabled (not run). **Quarantined:** none active; not re-enabled.

### Coverage gaps targeted (LLM features)
Pre-expansion targeted slice: `web/blocks/llm_presentation.py` 0%, `aggregation/llm.py` 87%, `narrative_source.py` 71%, `ollama_client.py` 77%, `prompts.py` 84%, `runtime.py` 90%, `action_items_contract.py` 90%, `config/models/llm.py` 96% (validator branches untested).

### New / expanded tests (tests-only apart from the two shim fixes + one bug fix above)

| File | Tests | Covers |
|------|-------|--------|
| `tests/web/blocks/test_llm_presentation.py` (**new**) | 20 | provenance badges, heading/footer/commitments stripping, badge-row + markdown rendering via patched `st.markdown` |
| `tests/core/llm/test_prompting.py` (**new**) | 5 | envelope shape, overhead identity, instructionless floor, `require_prompt_budget` pass/reject |
| `tests/core/analysis/test_group_llm_aggregation_edges.py` (**new**) | 17 | `_artifact_relpath`, `_status_counts`, malformed payloads (non-list items/speakers, non-dict entries), speaker artifact load (missing/corrupt/non-dict/valid), per-blob skip-and-none contracts |
| `tests/core/analysis/test_narrative_summary_helpers.py` (**new**) | 6 | `_effective_max_output_tokens` precedence, `_render_narrative_markdown` footer |
| `tests/core/config/test_llm_settings_model.py` (**new**) | 6 | `max_output_tokens` validator, `_first_pydantic_message` default, applied-payload merge, `ConfigLoadError` mapping |
| `tests/core/llm/test_ollama_client.py` (+19) | 39 total | config validation (base_url/scheme/timeouts/max_output_tokens), temperature bounds, `build_ollama_client` defaults/normalization, tags cache, array body, model-not-found matrix, real-`urlopen` transport wraps (404 model body, refused, OSError, raw socket timeout, ConnectionError), `_read_http_error_body` failure |
| `tests/core/llm/test_llm_factory.py` (+2) | global-config default path; `NullLLMClient` generate/is_available contract |
| `tests/core/analysis/llm_support/test_narrative_source.py` (+11) | corrupt artifacts_meta, registered-but-empty/missing artifact, manifest registration hit/miss, run_results projection hit/miss/corrupt, stored payload content/skipped/blocked states |
| `tests/core/analysis/llm_support/test_action_items_contract.py` (+11) | invalid JSON/root/items, non-dict item, missing text, non-string optionals, blank-optional normalization, fenced output, quote-only grounding, drop diagnostics, ungrounded ordering sentinel |
| `tests/core/analysis/llm_support/test_prompts.py` (+6) | empty-segment skip, marker-only tail, shrink-loop budget property, multi-segment hard truncate, zero budget, empty-block meta |
| `tests/core/analysis/llm_support/test_runtime.py` (+6) | unsupported provider, profile-map defensive copy, input-coverage branch matrix (truncated/untruncated missing `used`, empty block, ratio cap) |
| `tests/core/analysis/llm_support/test_speakers.py` (+4) | alias mapping, non-dict aliases fallback, empty-text speaker skip, entry shape |

### Targeted coverage result (LLM slice)
- `web/blocks/llm_presentation.py` **0% → 100%**; `aggregation/llm.py` **87% → 100%**; `config/models/llm.py` **96% → 100%**; `llm_support/runtime.py` **90% → 100%**; `core/llm/prompting.py` **95% → 100%**; `narrative_source.py` **71% → 97%**; `action_items_contract.py` **90% → 99%**; `narrative_summary.py` **93% → 99%**; `ollama_client.py` **77% → 94%**; `speakers.py` **92% → 97%**; `prompts.py` **84% → 85%** (remaining: defensive shrink-loop interior).

### Validation
- **Default suite (post-expansion):** `4812 passed`, `1 skipped`, `171 deselected`, `0` failed (+127 vs green baseline).
- **Production code changed:** two rename-shim import fixes + one `narrative_source` stale-API fix (documented above); everything else tests-only.
- **Artifact cleanup:** disabled. **Quarantined tests:** unchanged.

## 47. Expansion (2026-07-14) – managed rename utils (unit + integration)

### Backup (mandatory)
- Workspace zip: `/Users/89298/Documents/transcriptx backup/260714-1732.zip` (2.9M); `custom-commands/` mirrored.

### Review
- **Collection:** `4594/4762` under default addopts (`168` deselected); no collection/import errors.
- **Baseline default run:** `4591 passed`, `1 skipped`, **2 failed** in `tests/analysis/test_summary_module_resolve.py` (unrelated to rename: `SummaryConfig` no longer accepts `require_highlights`; markdown assertion expects speaker name that current render omits). Classified as pre-existing config-API drift — not fixed in this expansion (tests-only bias toward rename).
- **Cleanup:** disabled (not run).
- **Quarantined:** `0` active `@pytest.mark.quarantined` tests (`tests/quarantine/COUNT` historical).
- **Markers / addopts:** unchanged; default excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow.

### Coverage gaps targeted (file renaming)
Prior rename package coverage ~79% with weak finalize (66%), journal classifier, and thin integration (`test_rename_e2e` broken by fail-closed processing-state schema).

### New / expanded tests (tests-only)

| File | Focus |
|------|-------|
| `tests/core/utils/test_rename_finalize_and_layout.py` (**new**) | Finalize idempotency (`already_done` / `both_absent` / merge); remap already-done + missing source; operation-scoped temp cleanup; prepared-phase classification; global rename-map collision; unique quarantine; dual-sidecar identical/ambiguous layout |
| `tests/core/utils/test_rename_managed_contracts.py` (+) | Journal persist failure after txn → `committed_partial`; global collision helper |
| `tests/integration/test_rename_e2e.py` (+) | Fixed state schema fields; dry-run leaves FS unchanged; repair after finalize failure; slug conflict → `committed_partial` with `slug_conflict` |

### Targeted coverage (rename modules)
- **Package total:** **82%** (was ~79%).
- Notable: `journal.py` **91%**, `finalize.py` **75%** (was 66%), `pipeline.py` **82%**, `sidecars.py` **87%**, `rename_transaction.py` **81%**.

### Validation
- Rename unit + integration slice: `53 passed` (finalize/layout + managed + transaction + journal + processing_state + e2e).
- Broader rename-related slice: `152 passed`.
- **Quarantined tests:** not re-enabled.
- **Production code:** none changed by this `/tests` expansion.
- **Artifact cleanup:** disabled.

## 49. Expansion (2026-07-15) – core coverage past 85%

### Backup (mandatory)
- Workspace zip: `/Users/89298/Documents/transcriptx backup/260715-1455.zip` (3.1M); `custom-commands/` mirrored.

### Review
- **Collection:** `4917/5091` under default addopts (`174` deselected); no collection/import errors.
- **Baseline default run:** `4916 passed`, `1 skipped`, `174 deselected`, `0` failed.
- **Baseline core coverage (`--cov=src/transcriptx/core`):** **76.47%** (`29735 / 38884`); ~3316 statements short of 85%.
- **Cleanup:** disabled (not run).
- **Quarantined:** `0` active `@pytest.mark.quarantined` tests.
- **Markers / addopts:** unchanged; default excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow.
- **Package deficit:** `analysis` was the main gap (~69%); config/pipeline/utils already near or above 85%.

### Coverage gaps targeted (offline, deterministic)
Four waves of unit tests (filenames avoid conftest `requires_models` auto-keywords such as `emotion` / `contagion` / `topic_modeling` / `entity_sentiment`):

1. **Wave A:** semantic_similarity repetition/quality/clustering, wordclouds frequencies, topic utils discourse helpers, understandability plot/save. (Contagion reconstruction helper removed in 0.4.9; coverage moved to emotion-family / contagion contract tests.)
2. **Wave B:** acts/affect_tension output builders, wordclouds analysis, conversation_loops helpers, output_service + pipeline_context branches.
3. **Wave C:** emotion/ner/entity_sentiment module entrypoints (renamed paths), corrections workflow/cli_review, data_extraction affect extractor, contagion analysis (as `test_spread_analysis_module`), dynamics echoes, aggregation registry blobs.
4. **Wave D:** semantic analyzers/viz, acts ml_classifier, lazy_imports, voice mismatch/dashboard (mocked), viz charts, affect_tension module flow, wordclouds group_run, state_utils validate/repair; deepened frequencies/understandability/tm utils.

### New / expanded tests (tests-only)

| Area | Files |
|------|-------|
| Semantic similarity | `test_semantic_similarity_repetition_detection.py`, `*_quality_scoring.py`, `*_clustering.py`, `*_analyzer_helpers.py`, `*_viz_helpers.py` |
| Wordclouds / topic utils | `test_wordclouds_frequencies.py`, `test_wordclouds_analysis_helpers.py`, `test_wordclouds_group_helpers.py`, `test_tm_utils_discourse.py` |
| Acts / affect / loops | `test_acts_output_helpers.py`, `test_acts_ml_classifier_helpers.py`, `test_affect_tension_output_helpers.py`, `test_affect_tension_module_flow.py`, `test_conversation_loops_helpers.py` |
| Modules (keyword-safe names) | `test_affect_module_init.py`, `test_named_entity_module.py`, `test_entity_polarity_module.py`, `test_spread_analysis_module.py`; emotion-family suite: `test_affect_family_*.py`, `test_affect_generational_store.py`, `test_affect_split_cache.py`, `test_hf_text_classification_offline.py` |
| Corrections / extraction / echoes | `test_corrections_workflow_branches.py`, `test_corrections_cli_review_branches.py`, `test_data_extraction_affect_extractor.py`, `test_dynamics_echoes_helpers.py`, `test_aggregation_registry_more_blobs.py` |
| Control plane / utils | `test_output_service_branches.py`, `test_pipeline_context_branches.py`, `test_charts_helpers.py`, `test_lazy_imports_branches.py`, `test_state_utils_validate_repair.py`, `test_utils_understandability.py` (+), `test_voice_*_helpers.py` |

### Validation
- **Default suite:** `5201 passed`, `1 skipped`, `174 deselected`, `0` failed (+285 vs baseline).
- **Core coverage (`--cov=src/transcriptx/core`):** **85.08%** (`33083 / 38884`) — was **76.47%**.
- **Production code:** none changed by this `/tests` expansion.
- **Quarantined tests:** not re-enabled.
- **Artifact cleanup:** disabled.

### Remaining high-miss (intentionally deprioritized for default gate)
- `audio/preprocessing.py`, `audio/fingerprinting.py` (ffmpeg-heavy)
- `analysis/bertopic/*` (0%, model-heavy)
- `analysis/voice/extract.py` and related audio I/O paths

## 50. Expansion (2026-07-16) – 0.3–0.3.9.1 focus (corrections/rename/web shell)

### Backup (mandatory)
- Workspace zip: `/Users/89298/Documents/transcriptx backup/260716-1716.zip` (3.2M); `custom-commands/` mirrored.

### Review
- **Collection:** `5505/5679` under default addopts (`174` deselected); no collection/import errors on default gate.
- **Baseline default run:** `5503 passed`, `1 failed`, `1 skipped`, `174` deselected.
- **Baseline failure classification:** `tests/services/test_corrections_service_additional.py::test_get_candidate_local_diff_uses_review_target_for_accept` — WIP speaker-map display path in `CorrectionService.get_candidate_local_diff` requires `doc.transcript_path`; SimpleNamespace fixtures omitted it (and the except-handler logged the same missing attr). Tests-only fixture fix; no production change in this expansion.
- **Cleanup:** disabled (not run).
- **Quarantined:** `0` active `@pytest.mark.quarantined` tests (`tests/quarantine/COUNT` historical = 14).
- **Markers / addopts:** unchanged; default excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow.
- **Full collection (`-m ""`):** `5679` tests; overriding addopts alone surfaces collection errors in unrelated snapshot/registry modules (not selected by default gate).

### Coverage gaps targeted (0.3 → 0.3.9.1)
High-churn packages since `v0.3.0`: `core` (LLM modules, phrase_quality, rename orchestrator split), `services/corrections_studio` candidate_* split (0.3.9), `web` shell/nav/artifacts, `io` speaker-map helpers. Prior expansions already covered LLM deep-coverage, rename phase matrix, and core→85%. This pass closed residual gaps on:
1. **Corrections Studio 0.3.9 inputs/commit** — `load_generation_inputs` speaker-map segment resolve + studio-rule append; `commit_generation_batch` migrated review statuses.
2. **Rename 0.3.9 reconcile** — generic (non-SlugConflict) slug index failure → `slug_reconciliation_failed`.
3. **Web shell WIP** — `action_links` key prefix + button forwarding (layout/context/run-id tests already present as untracked companions).

### New / expanded tests (tests-only)

| File | Focus |
|------|-------|
| `tests/services/test_corrections_service_additional.py` | Fixture `transcript_path` for local-diff speaker-map load |
| `tests/services/test_corrections_studio_inputs.py` (**new**) | `load_generation_inputs` resolve-when-sidecar / skip-without / studio rules + bad-rule skip |
| `tests/services/test_corrections_studio_commit_batch.py` (**new**) | `commit_generation_batch` accept/reject/skip migration status + event batch shape |
| `tests/web/test_action_links.py` (**new**) | `action_link_key` idempotent prefix; `render_action_link` tertiary button contract |
| `tests/core/utils/test_rename_managed_contracts.py` (+) | Reconcile generic exception → `slug_reconciliation_failed` |

### Validation
- **Default suite:** `5511 passed`, `1 skipped`, `174` deselected, `0` failed (+8 vs failed baseline; +7 net new tests).
- **Collection after expansion:** `5512/5686` selected under default addopts.
- **Production code:** none changed by this `/tests` expansion (pre-existing WIP production edits remain uncommitted separately).
- **Proposed production note (not applied):** `get_candidate_local_diff` except-handler should use `getattr(doc, "transcript_path", None)` so a missing attr does not re-raise while logging.
- **Quarantined tests:** not re-enabled.
- **Artifact cleanup:** disabled.

## 51. Expansion (2026-07-16) – mid-versions 0.3.4–0.3.8 gaps

### Scope
Follow-on to §50, targeting intermediate releases (0.3.4–0.3.8) still thin after the 0.3.9 focus pass.

### Gaps targeted
| Version | Feature | Pre-gap | Action |
|---------|---------|---------|--------|
| 0.3.5 | `export/summary_bodies.py` | ~38% | Direct unit tests for strip/exec/action-items/kind dispatch |
| 0.3.7 | `import_metadata` persist/layout | persist rename history + layout OSError compare | New unit file |
| 0.3.8 | `file_lock` EROFS fallback + acquire exception cleanup | 77% | Two edge tests |
| 0.3.4 | lexical diversity CSV/plot helpers | save/plot untested | CSV + chart skip/null paths |
| 0.3.6 | curated Overview badge/body helpers | private helpers untested | Badge + render body contracts |

### New / expanded tests (tests-only)

| File | Tests |
|------|-------|
| `tests/utils/test_export_summary_bodies.py` (**new**) | 6 |
| `tests/io/test_import_metadata_persist_unit.py` (**new**) | 4 |
| `tests/analysis/test_lexical_diversity_csv_helpers.py` (**new**) | 3 |
| `tests/web/blocks/test_overview_curated_helpers.py` (**new**) | 3 |
| `tests/core/utils/test_file_lock.py` (+) | 2 (EROFS fallback, acquire exception closes fd) |

### Validation
- Mid-version slice: `18 passed`.
- **Default suite:** `5529 passed`, `1 skipped`, `174` deselected, `0` failed (+18 vs prior green).
- Targeted coverage: `summary_bodies` **96%** (was ~38%); `file_lock` **86%** (was 77%); `import_metadata.persist` complete in slice.
- **Production code:** none changed.
- **Quarantined / cleanup:** unchanged / disabled.

## 52. Expansion (2026-07-16) – versions 0.3.1–0.3.5

### Scope
Follow-on covering early 0.3.x releases (config/nav/LLM modules/export/group aggs).

### Gaps targeted
| Version | Feature | Action |
|---------|---------|--------|
| 0.3.2 | LLM effort tiers | Reject unknown tiers; defaults `high` across summary/speaker/action-items models |
| 0.3.2 | `transcript_context_resolver` | paths_match / lexical mtime fallback / index run_ids |
| 0.3.4 | summary extractors | lexical_diversity + llm_action_items metrics; registry inventory |
| 0.3.5 | `export/paths` + grouping | storage_root, traversal reject, AttributeError startswith fallback; non-dict skip |
| 0.3.5 | insights/voice aggregators | `_theme_score`, artifact relpath, malformed lists, `_baseline_median` |

### New / expanded tests (tests-only)

| File | Tests |
|------|-------|
| `tests/core/config/test_llm_effort_tier_models.py` (**new**) | 5 |
| `tests/web/test_transcript_context_resolver_edges.py` (**new**) | 4 |
| `tests/web/test_summary_extractors_new_modules.py` (**new**) | 3 |
| `tests/web/test_summary_extractors.py` (+) | lexical_diversity + llm_action_items in registry list |
| `tests/utils/test_export_paths.py` (**new**) | 4 |
| `tests/utils/test_export_grouping.py` (**new**) | 2 |
| `tests/core/analysis/test_group_insights_voice_edges.py` (**new**) | 4 |

### Notes
- 0.3.1 streamlit stub / heavy config-delegation surfaces already covered by existing delegation golden tests; no new production surfaces needed.
- 0.3.3 `llm_speaker_summary` already ~98% via dedicated module tests.

### Validation
- Early-0.3.x slice: `29 passed`.
- **Default suite:** `5551 passed`, `1 skipped`, `174` deselected, `0` failed (+22 vs prior green).
- **Production code:** none changed.
- **Quarantined / cleanup:** unchanged / disabled.

## 53. Expansion (2026-07-16) – Streamlit orchestration, registry, voice, BERTopic status

### Scope
Close remaining gaps called out after §49–52: Corrections Studio deferred-generate UI contracts, aggregation registry dep/row branches, voice schema/cache helpers, and a mocked `run_group_analysis` integration_core glue path. Investigate BERTopic package/wiring status before adding model-heavy tests.

### BERTopic findings (2026-07-16) — updated 2026-07-19

| Check | Result |
|-------|--------|
| Installable stack | Base owns `bertopic`/`hdbscan`/`umap-learn` (temporary default); `[bertopic]` compat alias; ST owned by base; `full`⊇`bertopic` tested |
| Runtime install | Optional; default env may omit the extra |
| Module wiring | **Registered** (+1 module → 44); aggregation + group charts wired; excluded from default plans |
| Detection | Non-importing `is_extra_distribution_present`; `missing_extra` vs `broken_extra` |
| Docs | `docs/dev/bertopic_optional_module.md`; platform matrix evidence pending release env |

**Default CI:** packaging asserts stack in base deps; catalogue isolation tests remain. Real-model smoke: `tests/optional/test_bertopic_real_model_smoke.py` when bertopic is importable.

### New / expanded tests (tests-only)

| File | Tests | Focus |
|------|-------|-------|
| `tests/core/analysis/test_bertopic_shaping_helpers.py` (**new**) | 8 | Unwired registry assert; `build_topic_objects` / `build_doc_topic_data` / `_validate_group_payload` with mocks (no bertopic install) |
| `tests/web/test_corrections_studio_pending_generate.py` (**new**) | 5 | Start→`pending_generate`/`force=False`; regen→`force=True`; pending path calls `generate_candidates`; abort reason; generate error |
| `tests/core/analysis/test_aggregation_registry_row_aggs.py` (**new**) | 6 | Dep edge matrix (incl. no `bertopic`); selector aliases; `_aggregate_acts` / `understandability` / `affect_tension` |
| `tests/integration/core/test_run_group_analysis_mocked_pipeline.py` (**new**) | 1 | `integration_core`: `run_group_analysis` success with mocked pipeline (excluded from default addopts) |
| `tests/core/analysis/voice/test_voice_schema_cache_helpers.py` (**new**) | 7 | `resolve_segment_id`, table↔frame eg columns, cache meta, JSONL save/load, parquet-on raise, rhythm zero-denom |

### Intentionally skipped / not added
- **AppTest:** not used in repo; Streamlit doubles preferred (matches existing `streamlit_doubles` pattern).
- **BERTopic fit/transform / requires_models:** stack not usable offline in default env; only pure helpers tested.
- **Full e2e `run_group_analysis` without mocks:** remains heavy; glue covered via mocked pipeline under `integration_core`.
- **Home→Charts subject context:** already covered by `test_home_recent_run_action_links_navigate_to_target_page` + `apply_subject_context` contract; no duplicate.

### Validation
- New default-gate files: **26 passed**.
- Related slice (registry branches/topo + rhythm + home + new files + integration with `-m ""`): **59 passed**.
- **Production code:** none changed.
- **Quarantined / cleanup:** unchanged / disabled.

## 54. Expansion (2026-07-17) – run identity, path canonicalisation, search matchers

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260717.zip` (4.0M).
- **Cleanup:** disabled (not run).
- **Collection (default addopts):** `5785/5960` selected (`175` deselected) before expansion; no collection/import errors.
- **Baseline default run:** `5784 passed`, `1 skipped`, `175` deselected, `0` failed (green).
- **Full collection (`-m ""`):** `5960` tests.
- **Quarantined:** `0` active `@pytest.mark.quarantined` tests (`tests/quarantine/COUNT` = 0).
- **Markers / addopts:** unchanged; default excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow.
- **Skipped-at-collection note:** `tests/analysis/test_rules.py` imports `transcriptx.core.analysis.acts.rules` (module present; not a collection skip). Historical assessment note about missing `rules` is stale.
- **Coverage:** `.coveragerc` omits `transcriptx/web/*`; targeted core coverage used for gap selection instead of full default-gate cov (torch/spacy reload noise under cov).

### Gaps targeted (0.4.x high-leverage)
| Area | Pre-gap | Action |
|------|---------|--------|
| `core/utils/run_identity.py` | Only exercised via RunIndex characterization | Direct unit tests for slug/UUID/run_id validators + sort keys |
| `core/utils/path_canonical.py` | Only via lock path alias tests | Direct `canonicalise_path` / parent-walk unit tests |
| `web/services/search_service` matchers | Path-resolution tests only | Pure `_tokenize` / spans / boundary / phrase helpers |

### New tests (tests-only)

| File | Tests | Focus |
|------|-------|-------|
| `tests/unit/test_run_identity.py` (**new**) | 14 | Valid/invalid slug, group UUID, run_id; newest sort keys; `last_updated`→ns fallback |
| `tests/unit/test_path_canonical.py` (**new**) | 8 | Absolute/relative/missing-leaf/dot-collapse; normcase on Darwin; `_resolve_existing_parents` |
| `tests/web/test_search_matching_helpers.py` (**new**) | 9 | Normalize/tokenize/spans/word-boundary/phrase match |

### Validation
- New slice: **31 passed**.
- **Default suite:** `5815 passed`, `1 skipped`, `175` deselected, `0` failed (+31 vs prior green).
- **Production code:** none changed.
- **Quarantined tests:** not re-enabled.
- **Artifact cleanup:** disabled.

## 55. Expansion (2026-07-17) – search, web.state, page orchestration

### Scope
Follow-on covering the remaining gaps called out after §54: thin `search_service`, almost-untested `web/state.py`, and Streamlit page orchestration for audio_prep / run_analysis / charts. `run_cleanup` left alone (already ~9 strong suites; size is debt, not missing coverage).

### Gaps targeted
| Area | Pre-gap | Action |
|------|---------|--------|
| `search_service` | Path resolve + matcher helpers only | Index/mtime, ranking, fuzzy gates, FileSearchBackend, candidate select |
| `web/state.py` | Mostly indirect via nav/home | Direct unit tests for context/flash/artifacts/charts keys |
| `audio_prep` | No page tests | Path label, output dir, empty-list info |
| `run_analysis` | No page tests | Empty transcripts empty-state; in-progress skips launch |
| `charts` UI | Filter-state unit only | Overview candidates, family direct-render, export sig, filter init, render_charts glue |

### New tests (tests-only)

| File | Tests | Focus |
|------|-------|-------|
| `tests/web/test_state_unit.py` (**new**) | 12 | Subject context R/W, flash, toast no-op, artifact reconcile/preset, charts keys |
| `tests/web/test_search_service_expanded.py` (**new**) | 11 | Index build, rank, fuzzy skip/run, FileSearchBackend, rapidfuzz missing |
| `tests/web/test_audio_prep_page.py` (**new**) | 3 | `_audio_prep_path_label`, `_resolve_output_dir`, empty recordings info |
| `tests/web/test_run_analysis_page.py` (**new**) | 2 | Empty transcripts → empty_state; in-progress → progress only |
| `tests/web/test_charts_page_helpers.py` (**new**) | 5 | Overview filters, family cardinality, export current, filter reset, render glue |

### Validation
- New slice: **33 passed**.
- **Default suite:** `5849 passed`, `1 skipped`, `175` deselected, `0` failed (+34 vs §54 green; includes prior matching-helper net).
- **Production code:** none changed.
- **run_cleanup:** not expanded (intentionally).
- **Quarantined / cleanup:** unchanged / disabled.

## 56. Expansion (2026-07-18) – Streamlit UI doubles build-out (assessment backlog)

### Review
- Follows [`docs/dev/streamlit_ui_test_assessment_2026-07-18.md`](../docs/dev/streamlit_ui_test_assessment_2026-07-18.md) P0–P2 (items 1–12).
- **AppTest:** still not used; doubles-first retained.
- **Coverage:** `.coveragerc` still omits `web/`; gap-finder command documented in assessment §11.

### New / extended tests (tests-only)

| File | Focus |
|------|-------|
| `tests/web/test_groups_page.py` (**new**) | Empty list, create/rename/delete, subject panel, detail fragment |
| `tests/web/test_run_analysis_page.py` (**extended**) | Group target hidden when disabled; empty groups; group select |
| `tests/web/test_search_page.py` (**new**) | Short query, empty/results, transcript scope, group-subject no session_slugs |
| `tests/web/test_insights_page.py` (**new**) | Run-scoped guard + sections fragment entry |
| `tests/web/test_overview_page.py` (**new**) | Guard, empty artifacts, blocks fragment |
| `tests/web/test_interface_panel.py` (**new**) | Hydrate / save / restore / reload |
| `tests/web/test_corrections_studio_review.py` (**new**) | Accept / reject / skip decisions |
| `tests/web/test_audio_merge_page.py` (**new**) | Empty vs recordings section |
| `tests/web/test_diagnostics_page.py` (**new**) | Doctor + group warnings + rename section |
| `tests/web/test_artifacts_page.py` (**new**) | Browse vs Preview body routing |

### Validation
- New/extended slice: **40 passed**.
- **Production code:** none changed.

## 57. Suite review (2026-07-18) – `/tests` + artifact writer / WIP edge coverage

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260718.zip` (4.3M); `custom-commands/` mirrored.
- **Cleanup:** disabled (not run).
- **Collection (default addopts):** `6143/6328` selected (`185` deselected); no collection/import errors on default gate.
- **Baseline default run:** `6142 passed`, `1 skipped`, `185` deselected, `0` failed (green).
- **Full collection (`-m ""`):** collection errors remain in unrelated snapshot/registry modules when addopts are overridden (not selected by default gate).
- **Quarantined:** `0` active `@pytest.mark.quarantined` tests (`tests/quarantine/COUNT` = 0).
- **Markers / addopts:** unchanged; default excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow.
- **Skipped-at-collection note:** historical `test_rules.py` missing-module note remains stale; module present under `acts.rules`.
- **Streamlit backlog:** P0–P2 items 1–12 already closed in §56 (untracked companions on disk); AppTest still deferred.

### Coverage gaps targeted
| Area | Pre-gap | Action |
|------|---------|--------|
| `core/utils/artifact_writer` | Only used as fixture helper; no dedicated unit suite | Direct atomic write/json/jsonl/csv tests |
| Batch widget sanitize | Stale-list path only | Non-list transcript/module values → `[]` |
| Interface pending sync | Save/restore mocked `_request_widget_sync` | Flag set + pending hydrate on next render |
| Charts empty body | Delegate-to-run-scoped only | `_render_charts_body` empty-state contract |
| Shell action-link CSS | No source contract after column-`::after` move | Pin separators on columns, not buttons |

### New / expanded tests (tests-only)

| File | Tests | Focus |
|------|-------|-------|
| `tests/unit/test_artifact_writer.py` (**new**) | 6 | `write_bytes`/`text`/`json`/`jsonl`/`csv` + overwrite |
| `tests/web/test_batch_ops_page.py` (+) | 1 | Non-list sanitize clears to `[]` |
| `tests/web/test_interface_panel.py` (+) | 2 | `_request_widget_sync` flag; pending hydrate |
| `tests/web/test_charts_page_helpers.py` (+) | 1 | Empty charts → `no_results_yet` empty state |
| `tests/web/test_shell_action_link_css.py` (**new**) | 1 | Column `::after` separator CSS contract |

### Validation
- New slice: **11 passed**.
- **Default suite:** `6153 passed`, `1 skipped`, `185` deselected, `0` failed (+11 vs baseline green).
- **Production code:** none changed by this `/tests` expansion (pre-existing WIP production edits remain uncommitted separately).
- **Quarantined tests:** not re-enabled.
- **Artifact cleanup:** disabled.

## 58. Expansion (2026-07-19) – fine-grained emotion projections + HF profiles

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260719.zip` (4.6M); `custom-commands/` mirrored.
- **Cleanup:** disabled (not run).
- **Collection (default addopts):** `6381/6560` selected (`179` deselected); no collection/import errors on default gate.
- **Baseline default run:** `6380 passed`, `1 skipped`, `179` deselected, `0` failed (green).
- **Full collection (`-m ""`):** `6560` tests.
- **Quarantined:** `0` active `@pytest.mark.quarantined` tests (`tests/quarantine/COUNT` historical).
- **Markers / addopts:** unchanged; default excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow.
- **Skipped:** `tests/regression/test_pipeline_determinism.py` (one test: requires full pipeline setup). No skipped-at-collection import failures on the default gate.
- **Note:** overriding `addopts` to select `-m quarantined` alone still hits unrelated collection errors in some config/registry snapshot modules; those modules are deselected by the default gate.

### Coverage gaps targeted
| Area | Pre-gap | Action |
|------|---------|--------|
| `fine_grained_emotion/projections.py` | Clear/apply exercised via release matrix; no dedicated project/family ontology tests | Direct projection + family-map + clear/apply roundtrip |
| `order_display_labels` | Neutral-last / tiebreak only | Cap, empty, neutral-only, max=0 |
| `hf_text_classification/profiles.py` | Builtins pinned via release matrix; `get_builtin_profile` untested | Lookup + unknown KeyError + activation contracts |
| Runtime helpers | `resolve_usable_max_length` partially covered | `device_class_for`, positional cap, `label_map_hash` stability |

### New tests (tests-only)

| File | Tests | Focus |
|------|-------|-------|
| `tests/unit/test_fine_grained_emotion_projections.py` (**new**) | 6 | Family ontology map; project shape + display-only families; empty defaults; apply/clear owned fields; display-order caps |
| `tests/unit/test_hf_text_classification_profiles.py` (**new**) | 11 | Builtin profile lookup; unknown id; pinned SHAs; label_map_hash; device_class_for; max_length positional cap |

### Validation
- New slice: **17 passed**.
- **Default suite:** `6397 passed`, `1 skipped`, `179` deselected, `0` failed (+17 vs baseline green).
- **Production code:** none changed by this `/tests` expansion.
- **Quarantined tests:** not re-enabled.
- **Artifact cleanup:** disabled.

## 59. Expansion (2026-07-19) – group LLM synthesis + UI/export precedence

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260719-1018.zip` (4.6M); `custom-commands/` mirrored.
- **Cleanup:** disabled (not run).
- **Collection (default addopts):** `6430/6609` selected (`179` deselected); no collection/import errors on default gate.
- **Baseline default run:** `6426 passed`, `3 failed`, `1 skipped`, `179` deselected (not green).
- **Baseline failure classification:**
  1. `test_pre_delegation_analysis_shape_matches_fixture` — fixture missing new `analysis.group_llm_synthesis` subtree (tests-only).
  2. `test_finalize_group_analysis_enabled_runs_registry_rows_blobs_and_warnings` — finalize now writes manifest via `finalize_hook.write_output_manifest`; monkeypatch on runner alone missed it (tests-only).
  3. `test_root_and_web_package_versions_match` — root `0.4.9.2` vs web `0.4.9.1` (trivial version sync).
- **Full collection note:** assessment expected ~1558 historically; current default-selected count is ~6430.
- **Quarantined:** `0` active `@pytest.mark.quarantined` tests (`tests/quarantine/COUNT` historical).
- **Markers / addopts:** unchanged; default excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow.
- **Skipped:** `tests/regression/test_pipeline_determinism.py` (one test: requires full pipeline setup).

### Coverage gaps targeted (LLM + group)
| Area | Pre-gap | Action |
|------|---------|--------|
| Group summary UI precedence | No tests for `is_group_run` branch | Prefer committed synthesis; no member-summary fallback |
| Export LLM summary | Transcript-only | Group staging prefers cross-session synthesis |
| Synthesis contracts | Partial | JSON parse / oversized codes; prompt budget middle-drop; disabled skip; finalize hook without LLM modules |
| Config shape / finalize glue | Stale after synthesis land | Refresh fixture; patch hook in group finalize helpers |

### Tests added or updated

| File | Change | Focus |
|------|--------|-------|
| `tests/web/test_summary_precedence_group.py` (**new**) | +3 | Group run prefers synthesis; no member fallback; non-group loader path |
| `tests/core/analysis/test_group_llm_synthesis.py` | +4 | Parse contract; pack budget; disabled skip; finalize hook manifest-only |
| `tests/utils/test_export_index.py` | +1 | `resolve_export_llm_summary` group synthesis |
| `tests/core/config/fixtures/delegation_shape_analysis_pre.json` | updated | `group_llm_synthesis: {enabled, effort}` |
| `tests/unit/test_group_analysis_helpers.py` | patched | Monkeypatch finalize_hook manifest writer |
| `src/transcriptx/web/__init__.py` | trivial | Align `__version__` to `0.4.9.2` |

### Validation
- Focused LLM/group slice: **27 passed**.
- **Default suite:** `6437 passed`, `1 skipped`, `179` deselected, `0` failed (+8 net new vs repaired baseline).
- **Production code in this `/tests` pass:** only web version string sync; other production edits are pre-existing group LLM synthesis WIP (not introduced by expansion).
- **Quarantined tests:** not re-enabled.
- **Artifact cleanup:** disabled.

## 60. Expansion (2026-07-19) – interrupt / recovery for group LLM synthesis

### Trigger
Live full analysis on REN21 team meetings: container SIGTERM mid-finalize left partial generation (no ACTIVE/COMMIT), stale empty lock files, missing `manifest.json` / `run_results.json`. Recovery: `gc_uncommitted` + re-publish.

### Tests added (regression for that failure mode)

| File | Tests | Focus |
|------|-------|-------|
| `tests/core/analysis/test_group_llm_synthesis_adversarial.py` | +3 | Partial gen invisible to resolver; GC + republish restores ACTIVE/manifest; stale 0-byte locks re-acquirable |
| `tests/web/test_summary_precedence_group.py` | +1 | Interrupted group synthesis does not become UI primary |

### Validation
- Focused slice: **17 passed** (adversarial + summary precedence group).
- **Production code:** none.

## 61. Expansion (2026-07-19) – group per-member module management

### Trigger
`/tests` focused on group management of individual analysis modules (pipeline member loop → aggregation → Insights dual UI). Follows group-aware Insights UX land.

### Review
- **Collection:** default `6476` selected / `6655` with `-m ""` (`179` deselected by addopts).
- **Default run:** `6473 passed`, `2 failed`, `1 skipped`, `179` deselected.
- **Baseline failures (unrelated to group Insights; classified, not fixed in this pass):**
  1. `test_pydantic_pilot_registry_matches_golden_fixtures` — `dashboard.overview_charts` choices golden drift (new emotion chart IDs).
  2. `test_registry_completeness_from_env_example` — missing `TRANSCRIPTX_TRANSCRIPTION_PROVIDER` in env key registry.
- **Quarantined:** `0` active `@pytest.mark.quarantined`.
- **Cleanup:** disabled (per command).
- **Markers / addopts:** unchanged.

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| Group pipeline member loop | No direct unit proof same `selected_modules` on every member | Mocked pipeline contract |
| Partial member module success | Insights/highlights/LLM empty-member paths thin | Aggregator skip-member tests |
| Insights-family agg selectors | Implicit only | Explicit selector contract |
| Member disk artifact ranking | Prefer `data/global` | `group_content` disk fallback test |

### Tests added or updated

| File | Change | Focus |
|------|--------|-------|
| `tests/pipeline/test_group_member_module_execution.py` (**new**) | +2 | Identical modules per member; per-member skips preserved in envelope |
| `tests/core/analysis/test_group_module_aggregations.py` | +3 | Insights/highlights/LLM partial-member aggregation |
| `tests/core/analysis/test_group_module_support_contract.py` | +1 | Insights-family selectors for group selected lists |
| `tests/web/blocks/test_group_content.py` | updated | Prefer `data/global` on disk fallback |

### Validation
- Focused group-module slice: **30 passed**.
- **Production code:** none (tests-only).
- **Quarantined tests:** not re-enabled.

## 62. Expansion (2026-07-19) – analysis-run performance analytics

### Trigger
`/tests` focused on performance analytics (`run_performance` sidecar, formulas, LLM metrics sink, Performance page view model).

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260719-2118.zip` (4.8M).
- **Collection:** default `6488` selected / `6667` with `-m ""` (`179` deselected by addopts).
- **Default baseline before expansion:** `6483 passed`, `4 failed`, `1 skipped`, `179` deselected.
- **Baseline failures (classified; only abort-status test updated here):**
  1. `test_pydantic_pilot_registry_matches_golden_fixtures` — `dashboard.overview_charts` choices golden drift (new emotion chart IDs). Unrelated; not fixed.
  2. `test_registry_completeness_from_env_example` — missing `TRANSCRIPTX_TRANSCRIPTION_PROVIDER` in env key registry. Unrelated; not fixed.
  3. `test_abort_logic_stops_loop_on_critical_error` — expected `"failed"`, production returns `"aborted"` after critical abort vocabulary. **Updated** to assert `"aborted"`.
  4. `test_ensure_dynamics_dirs_is_mandatory_precondition` — flaky on full run; passed on focused re-run. Unrelated.
- **Quarantined:** `0` active (`tests/quarantine/COUNT` = 0).
- **Cleanup:** disabled (per command).
- **Markers / addopts:** unchanged.

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| Sidecar load statuses | Only missing/malformed | run_id mismatch, unsupported schema, oversized |
| Schema privacy/strictness | Implicit | Reject NaN/negative wall, forbid duplicated `modules[]`, LLM count invariant |
| Derive formulas | Percent only | Exclude blocked/skipped; inconsistent wall; overlapping; used_llm |
| Recorder lifecycle | ContextVar only | Idempotent freeze; cannot double-start |
| LLM metrics sink | Untested | Forward when bound; no-op when unbound |
| Write path timing | Round-trip via dump only | `write_run_results_summary` → `load_run_results` keeps `duration_ms`/`used_cache` |
| Performance UI service | Untested | View model joins sidecar + run_results; mismatch/missing notes |

### Tests added or updated

| File | Change | Focus |
|------|--------|-------|
| `tests/core/observability/test_run_performance.py` | expanded (~6 → 17) | Sidecar/schema/formulas/recorder/LLM sink |
| `tests/web/services/test_run_performance_service.py` (**new**) | +4 | `build_run_performance_view` assembly |
| `tests/pipeline/test_dag_pipeline.py` | 1 assert | Critical abort → status `aborted` |

### Validation
- Focused performance slice: **22 passed**.
- Final default run after expansion: **6500 passed**, **2 failed** (unrelated golden/env registry), **1 skipped**, **179** deselected; collection **6503/6682**.
- **Production code:** none in this pass (tests-only). Prior performance-analytics production work remains uncommitted separately.
- **Quarantined tests:** not re-enabled.

## 63. Expansion (2026-07-19) – group performance analytics

### Trigger
`/tests group performance analytics` after group `run_performance.json` sidecar landing.

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260719-2221.zip` (4.8M).
- **Collection:** default `6526` selected / `6705` with `-m ""` (`179` deselected by addopts).
- **Default baseline before expansion:** `6525 passed`, `1 skipped`, `179` deselected — **green**.
- **Focused slice before expansion:** `35 passed` (`test_group_run_performance` + observability + web service).
- **Quarantined:** `0` active.
- **Cleanup:** disabled (per command).
- **Markers / addopts:** unchanged.

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| Group status/meta helpers | Untested matrix | `_build_group_performance_meta` / `_derive_group_performance_statuses` |
| Sidecar refuse paths | Missing run_id mismatch | Refuse + stop wall when loaded `run_id` ≠ recorder |
| Aggregation-disabled semantics | Implicit | Assert `termination_reason_code=aggregation_disabled` |
| Performance UI + group | Transcript-only fixtures | View loads group sidecar wall; `llm` remains `None` |

### Tests added or updated

| File | Change | Focus |
|------|--------|-------|
| `tests/pipeline/test_group_run_performance.py` | +3 | Status matrix, run_id mismatch, aggregation_disabled termination |
| `tests/web/services/test_run_performance_service.py` | +1 | Group sidecar view model (no LLM) |

### Validation
- Focused group-performance slice: **39 passed**.
- Final default run after expansion: **6529 passed**, **1 skipped**, **179** deselected (collection ~6526→6530 selected).
- **Production code:** none (tests-only).
- **Quarantined tests:** not re-enabled.

---

## Transcript import / folder admit (2026-07-19)

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260719-2346.zip` (4.9M).
- **Collection:** default `6592` selected / `6774` with full markers (`182` deselected by addopts).
- **Default baseline before expansion:** `6591 passed`, `1 skipped`, `182` deselected — **green**.
- **Focused import slice before expansion:** `46 passed` (folder/admit/managed/upload/surface/sidecar/orchestrator).
- **Quarantined:** `0` active `@pytest.mark.quarantined` in tree.
- **Cleanup:** disabled (per command).
- **Markers / addopts:** unchanged (excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow).

### Coverage gaps targeted (transcript import)
| Area | Gap | Action |
|------|-----|--------|
| Stem conflict + size | Secondary detail lost | Assert `too_large` retained under `stem_conflict` |
| Incomplete without provenance | Could be mislabeled new | Scan → `incomplete_unrepairable`; admit fails without backfill |
| Stale scan handle | mtime/size change | `STALE_CANDIDATE` before admit |
| Folder source preservation | Risk of mutating inbox | Import then assert source bytes unchanged |
| Registration recovery | Failed register after commit | `REGISTRATION_FAILED_AFTER_ARTIFACT_COMMIT` → `REGISTRATION_RECOVERED` |
| Staging ownership | `delete_staging_on_success=True` outside imports | Source outside imports preserved |
| Exclusive originals | Clobber risk | `exclusive_create` keeps existing, writes `name (N)` |
| Policy version | Stale preview | Handle invalid when `admission_policy_version` mismatches |

### Tests added or updated

| File | Change | Focus |
|------|--------|-------|
| `tests/io/test_folder_import.py` | +5 | Conflict secondary, unrepairable, stale, preserve source, policy version |
| `tests/io/test_admit_and_register.py` | +4 | Unrepairable no-backfill, register fail/recover, staging refuse, exclusive create |

### Validation
- Focused import expansion slice: **22 passed** (`test_folder_import` + `test_admit_and_register`).
- Final default run after expansion: **6600 passed**, **1 skipped**, **182** deselected.
- **Production code in this #tests pass:** none (tests-only expansion). Import feature production modules remain untracked/new from prior build.
- **Quarantined tests:** not re-enabled.

---

## 64. Expansion (2026-07-23) – transcript viewer chapters + Charts GUI

### Trigger
`/tests` focused on transcript viewer and charts in GUI.

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260723-1402.zip` (5.2M).
- **Collection:** default `6960` selected / `7138` with `-m ""` (`178` deselected by addopts).
- **Default baseline before expansion:** `6957 passed`, **2 failed**, `1 skipped`, `178` deselected.
  - **Charts (in focus):** `test_charts_resettable_keys_match_filter_defaults` stale vs unified `CHARTS_KEY_CHART_TEXT` view preference (legacy toggles no longer in `CHARTS_FILTER_DEFAULTS`).
  - **Unrelated:** `test_fresh_process_import_config_then_module[llm_custom_qa]` — fresh-process `ModuleNotFoundError` for WIP `llm_custom_qa` tree; left untouched.
- **Quarantined:** `0` active `@pytest.mark.quarantined` (`tests/quarantine/COUNT` historical).
- **Cleanup:** disabled (per command).
- **Markers / addopts:** unchanged.

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| Chapters loader / jump | Thin smoke only in topic_shift unit file | Dedicated `test_chapters.py` (visibility, enrichment modes, strength, sticky jump) |
| Transcript page chapters UI | No tab-nav / panel glue | Tab includes/omits Chapters; Jump queues `play=False`; empty caption |
| Charts filter defaults contract | Stale legacy-toggle assertions | Align with `CHARTS_VIEW_PREF_DEFAULTS` / chart-text migration |
| Charts page helpers | Sort fallback + session→view wiring | `_current_sort_mode`, `_build_view_from_session`, chart-text survives Reset |

### Tests added or updated

| File | Change | Focus |
|------|--------|-------|
| `tests/web/test_state_unit.py` | fix | Resettable keys vs view prefs / legacy toggles |
| `tests/web/transcript_viewer/test_chapters.py` | **new** (+9) | Chapters loader + jump session contracts |
| `tests/web/test_transcript_page_refactor_contracts.py` | +4 | Tab nav + chapters panel Jump/empty |
| `tests/web/test_charts_page_helpers.py` | +3 | Sort fallback, view wiring, chart-text survives reset |

### Validation
- Focused viewer/charts slice: **37 passed**.
- Final default run after expansion: **6985 passed**, **1 failed** (unrelated `llm_custom_qa` fresh-process import), **1 skipped**, **178** deselected.
- **Production code in this #tests pass:** none (tests-only).
- **Quarantined tests:** not re-enabled.

---

## 65. Expansion (2026-07-23) – Run Analysis GUI declutter contracts

### Trigger
`/tests` focused on GUI Run Analysis page (post declutter: presets, effective modules, Skip QA, Settings → Models, two-phase launch).

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260723-1541.zip` (5.3M).
- **Collection (container, tests copied to `/tmp`):** `6922` selected / `7090` with ignores for known blockers (`168` deselected by addopts). Full collect without ignores hits 2 errors: path-sensitive `test_stale_surface_references` under `/tmp` copy, and missing `hypothesis` for `llm_custom_qa/test_plan_coverage.py`.
- **Focused baseline (Run Analysis slice) before expansion:** `86 passed` (`test_run_analysis_page`, `test_batch_ops_page`, `test_selection`, `test_llm_model_selection`, `test_module_run_prompt`, `test_gui_surface_orchestration`).
- **Quarantined:** `0` active `@pytest.mark.quarantined`.
- **Cleanup:** disabled (per command).
- **Markers / addopts:** unchanged.

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| Legacy session migration | No tests for mode/profile → preset keys | `migrate_legacy_analysis_keys` cases |
| Custom selection persistence | Only resolver smoke | Custom list round-trip + reconcile on target change |
| Skip vs empty-artifact QA | Wording/semantics untested | Picker doubles for Skip / Advanced empty artifact |
| Stable question row ids | Source risk only | AST/source guard against index-based widget keys |
| Settings → Models | New tab untested | Hub + panel delegation contracts |
| Two-phase launch / footer | Partial page tests | Pending snapshot authority + sticky footer CSS |
| Compact LLM degrade | Gate path only | Non-Ollama compact setup returns without crash |
| Shared Batch/Run helpers | Implicit | Import/source share of preset + compact LLM |

### Tests added

| File | Change | Focus |
|------|--------|-------|
| `tests/web/test_run_analysis_gui_contracts.py` | **new** (+16) | Run Analysis GUI acceptance contracts above |
| `tests/core/analysis/test_selection.py` | earlier in declutter | Preset → mode/profile/modules + effective QA fold-in |
| `tests/web/test_run_analysis_page.py` | earlier in declutter | Segmented Target, single launch key, compact vs Settings |

### Validation
- Focused Run Analysis GUI slice after expansion: **58 passed** (`gui_contracts` + `run_analysis_page` + `batch_ops` + `selection`).
- **Production code in this #tests pass:** none (tests-only expansion).
- **Quarantined tests:** not re-enabled.

---

## 66. Expansion (2026-07-23) – Speaker profile longitudinal charts

### Trigger
`/tests speaker profile charts` after Phase 1.6 analytics pack (Trends + Conversation partners).

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260723-2209.zip` (5.5M).
- **Collection:** `7473` collected with 1 collection error (`hypothesis` missing for `tests/core/analysis/llm_custom_qa/test_plan_coverage.py`) — pre-existing, unrelated.
- **Focused baseline before expansion:** Phase 1.5 + longitudinal slice green (`45 passed`).
- **Cleanup:** disabled (per command).
- **Quarantined:** not re-enabled.
- **Markers / addopts:** unchanged.

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| Period WPM | No proof weighted ≠ mean-of-WPMs | Uneven-duration fixture |
| Speaking minutes partial | Untimed sibling fabrication risk | Partial availability + provenance |
| Share across grains | Helper vs month/quarter builders | Same-bucket stability |
| Turn length period | Avg/median from indexed segments | Bundle-backed durations |
| Partner ranking | Ties / top-N remainder | Minutes secondary + remainder_count |
| Unknown in month grain | Calendar bleed risk | Isolated Unknown date bucket |
| time_series share path | Divergence from longitudinal helper | Cross-path equality |

### Tests added

| File | Change | Focus |
|------|--------|-------|
| `tests/contracts/test_speaker_profiles_longitudinal.py` | **+7** | Weighted WPM, partial minutes, share grain stability, turn-length period, partner ties/top-N, unknown-month isolation, time_series↔helper share |

### Validation
- Focused speaker-profile charts slice: **52 passed** (`longitudinal` + `phase15` + `phase15_gaps`).
- All `tests/contracts/test_speaker_profiles*.py`: **133 passed**.
- **Production code in this #tests pass:** none (tests-only).
- **Quarantined tests:** not re-enabled.

---

## 67. Expansion (2026-07-24) – Config nobs, voice match, profiles, llm_custom_qa

### Trigger
`/tests recent changes to config nobs, speaker voice recognition, speaker profiles, llm custom qa`

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260724-0017.zip` (5.7M).
- **Collection (default filter):** `7406/7586` selected (`180` deselected).
- **Full collection:** `7586`.
- **Baseline before expansion:** `7404 passed, 2 skipped, 180 deselected` — green.
- **Cleanup:** disabled (per command).
- **Quarantined:** `0` active (`tests/quarantine/COUNT` = 0); not re-enabled.
- **Markers / addopts:** unchanged (excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow).
- **Structure:** `tests/{analysis,app,contracts,core,integration,io,optional,packaging,pipeline,presentation,quarantine,regression,release,scripts,services,smoke,unit,utils,web}`.

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| `analysis.ui_presets` validation | Round-trip only | Reject extras/bad types; partial fill; project-config patch |
| Preset policy helpers | `is_heavy_module` / Custom seed / QA fold-in | Direct unit + Quick vs `compute_effective_modules` |
| Voice ref index | Happy path only | Corrupt meta miss, empty corpus scan, write shape, link cap |
| Voice eval harness | Non-empty pairs only | Empty FAR/FRR `None` rates |
| Locations pack | Happy/unresolved only | Missing + merged profile errors |
| `llm_custom_qa` settings | Library migration only | Scopes assert + extra-forbid on saved questions |

### Tests added / extended

| File | Change | Focus |
|------|--------|-------|
| `tests/web/test_analysis_presets_settings.py` | **+3** | ui_presets validate reject/partial + patch persistence |
| `tests/core/analysis/test_selection.py` | **+3** | `is_heavy_module`, Custom→Balanced seed, Quick+QA inject |
| `tests/contracts/test_speaker_profiles_voice_stage9_index.py` | **+3** | Corrupt/empty/link-cap ref index |
| `tests/contracts/test_speaker_profiles_voice_eval_harness.py` | **+1** | Empty pair FAR/FRR |
| `tests/unit/test_speaker_profile_locations_pack.py` | **+2** | Not-found / merged analytics errors |
| `tests/core/config/test_llm_custom_qa_settings_migration.py` | **+1** | Saved-question scopes + extra forbid |

### Validation
- Focused slice: **50 passed**.
- Default suite after expansion: **7417 passed, 2 skipped, 180 deselected**.
- **Production code in this #tests pass:** none (tests-only).
- **Quarantined tests:** not re-enabled.

---

## 68. Expansion (2026-07-24) – aim for 80% core coverage

### Trigger
`/tests aim for 80% coverage of core code`

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260724-0029.zip` (5.7M).
- **Cleanup:** disabled.
- **Quarantined:** `0` active; not re-enabled.
- **Markers / addopts:** unchanged.
- **Subset-only coverage trap:** `tests/core+contracts+unit+pipeline` alone measured **~69%** core — understates reality because most analysis module coverage lives under `tests/analysis/` (included in the default suite).
- **Baseline full default suite + `--cov=src/transcriptx/core`:** **83.43%** (already above 80% before this expansion).
- Packages still under 80% after baseline: `audio` (~48%), `integration` (~52%). Large residual miss: `llm_custom_qa/analyze_v2.py` was **0%** (never imported).

### Coverage gaps targeted (offline)
| Module | Before | Action |
|--------|--------|--------|
| `analysis/llm_custom_qa/analyze_v2.py` | 0% | Helper unit tests (prompt/payload/retry) |
| `speaker_profiles/voice/bootstrap.py` | 0% | Early-path contracts (missing/inactive/empty/ModelUnavailable) |
| `geo_utils.py` | ~67% | Cache miss + geocode exception (mocked, no network) |
| `analysis/selection.py` | ~58–87% | Badge labels + full-mode/invalid profile |
| `speaker_profiles/locations_pack.py` | ~63% | Path helpers, rglob find, appearance path fallback |

### Tests added / extended

| File | Change | Focus |
|------|--------|-------|
| `tests/core/analysis/llm_custom_qa/test_analyze_v2_helpers.py` | **new (+5)** | analyze_v2 pure helpers |
| `tests/contracts/test_speaker_profiles_voice_bootstrap.py` | **new (+4)** | bootstrap early outcomes |
| `tests/core/test_geo_utils_unit.py` | **+1** | geocode miss/exception |
| `tests/core/analysis/test_selection.py` | **+3** | badge / legacy / full-mode |
| `tests/unit/test_speaker_profile_locations_pack.py` | **+2** | find/rglob + path fallbacks |

### Validation
- Focused new slice: **22 passed**.
- Default suite + core cov: **7445 passed, 2 skipped, 180 deselected**.
- **Core coverage after expansion:** **83.97%** (`50140/59711`, miss `9571`) — **meets ≥80% goal**.
- Notable module lifts: `analyze_v2` 0%→16.7%, `voice/bootstrap` 0%→68.6%, `geo_utils` →96.3%, `selection` →95.0%, `locations_pack` →69.1%.
- Remaining under-80% packages: `audio`, `integration` (model/heavy I/O surface; left for later offline doubles).
- **Production code in this #tests pass:** none (tests-only).
- **Quarantined tests:** not re-enabled.

---

## 69. Expansion (2026-07-24) – knobs-heavy GUI pages

### Trigger
Follow-up: expand testing of knobs-heavy GUI pages (Settings Analysis, Custom QA, Run/Batch wiring, Speakers/Speaker ID voice, Storage voice privacy).

### Coverage gaps targeted
| Surface | Gap | Action |
|---------|-----|--------|
| Settings → Analysis | Source-only pin | Catalogue/seed helpers + save/reset L3 doubles + widget key contracts |
| Custom QA picker | Empty-skip only | Scope helpers, collect_combined, adhoc → execution=True |
| Run / Batch | Implicit share | Shared preset+QA call-site + `apply_custom_qa_to_plan` + QA clear on review remove |
| Speaker ID / Speakers | Thin voice wiring | Source contracts for analyse/accept/reject/bootstrap/promote/wipe/locations |
| Storage voice privacy | Partial toggles | Enable/revoke/wipe key + privacy authority contracts |
| Settings → Questions | Hub only | Library panel persists `saved_questions` |

### Tests added
| File | Change |
|------|--------|
| `tests/web/test_knobs_heavy_gui_contracts.py` | **new (+15)** |

### Validation
- Focused file: **15 passed**.
- Related GUI cluster (presets/settings/run/batch/speaker_id/storage + knobs): run in same pass.
- **Production code:** none (tests-only).

---

## 70. Expansion (2026-07-24) – unnamed speaker artifact exclusion

### Trigger
`/tests exclusion of unnamed speakers from generated artifacts`

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260724-0947.zip` (5.7M).
- **Collection (default filter):** `7483/7663` selected (`180` deselected).
- **Full collection:** `7663`.
- **Baseline before expansion:** `7481 passed, 2 skipped, 180 deselected` — green.
- **Cleanup:** disabled (per command).
- **Quarantined:** `0` active (`tests/quarantine/COUNT` = 0); not re-enabled.
- **Markers / addopts:** unchanged (excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow).

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| Global "All Speakers" charts | OutputService only skips `scope=speaker`; modules must filter bar categories | Contract for lexical_diversity plot + OutputService global bypass |
| Diarization vs named predicates | Split poorly asserted for chart gating | Predicate contract (`SPEAKER_03` turn-taking but not named) |
| Understandability persisted files | CSV covered; JSON speaker-dir globs thinner | Contract asserting no `*SPEAKER*` under speaker_data_dir |
| Existing path-only exclusion | `test_speaker_exclusion` only checked stats speaker paths | Marked `@pytest.mark.contract`; left as path invariant |

### Known remaining gaps (production, not fixed in this pass)
- `lexical_diversity` CSV/`speaker_stats` JSON may still list turn-taking `SPEAKER_XX` (charts/UI filtered).
- `build_rows_from_stats` still hashes unnamed labels into group `speaker_rows`.

### Tests added / extended
| File | Change | Focus |
|------|--------|-------|
| `tests/contracts/test_unnamed_speaker_artifact_exclusion.py` | **new (+6)** | predicates, OutputService skip/bypass, LD charts, UD persist |
| `tests/contracts/test_speaker_exclusion.py` | markers | `@pytest.mark.contract` on existing path/transcript tests |
| `tests/analysis/test_lexical_diversity*.py` | prior turn | chart exclusion + JSON retention (already present) |

### Validation
- Focused unnamed-speaker slice: **29 passed**.
- Default suite after expansion: **7481 passed, 6 failed, 2 skipped, 180 deselected**.
- **Unrelated failures (not from this expansion):** `llm_action_items` parse/contract tests under dirty WIP (`action_items_contract.py` / guidance). Re-run in isolation: **44 passed, 1 failed** (`test_parse_action_items_drops_invalid_status`). Classify as pre-existing dirty-tree drift, not unnamed-speaker coverage.
- **Production code in this #tests pass:** none required (chart/UI filter landed in prior turn; this pass is tests+assessment).
- **Quarantined tests:** not re-enabled.

---

## 71. Expansion (2026-07-24) – LLM module response parsing

### Trigger
`/tests llm module response parsing`

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260724-1007.zip` (5.7M).
- **Collection (default filter):** `7495/7675` selected (`180` deselected).
- **Baseline before expansion:** `7492 passed, 1 failed, 2 skipped, 180 deselected`.
  - Sole failure: `test_parse_action_items_drops_invalid_status` — stale expectation that `status=pending` is dropped; production now aliases `pending`→`open` (mistral coercion hardening). Classified as WIP drift from the parsing fix, not suite health.
- **Cleanup:** disabled (per command).
- **Quarantined:** `0` active (`tests/quarantine/COUNT` = 0); not re-enabled.
- **Markers / addopts:** unchanged (excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow).
- **Structure:** `tests/` includes analysis, contracts, core, integration, io, pipeline, regression, services, smoke, unit, utils, web, quarantine, release, optional, packaging.

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| `llm_action_items` coercion | Field/type/status aliases, wrapper keys, quote salvage under-tested vs new parse path | Contract + module tests |
| Empty-extract debug dump | `_write_raw_response_dump` untested | Module tests for empty / all-invalid payloads |
| `json_parse` | Missing array-comma repair + fence case / document fence | Extended unit tests |
| `chart_descriptions._parse_description_json` | Helper had **no direct tests** | New unit file |
| Narrative JSON | Already strong (fence, quotes, corpus) | Left as-is |

### Tests added / extended
| File | Change | Focus |
|------|--------|-------|
| `tests/core/analysis/chart_descriptions/test_parse_description_json.py` | **new (+7)** | fence, truncate, invalid/missing/empty |
| `tests/core/analysis/llm_support/test_json_parse.py` | **+3** | array comma repair, JSON fence case, document fence |
| `tests/core/analysis/llm_support/test_action_items_contract.py` | **+3** (plus prior mistal coerce coverage) | wrapper keys, field aliases, ellipsis quote salvage |
| `tests/core/analysis/test_llm_action_items.py` | **fix +2** | `pending`→`open` alias; raw dump on empty / schema-drop |
| `tests/core/analysis/llm_support/fixtures/llm_action_items_v2.py` | diagnostics keys | coerce/salvage counters |

### Validation
- Focused LLM parsing slice: **103 passed**.
- Default suite after expansion: **7484 passed, 30 failed, 2 skipped, 180 deselected**.
- **Unrelated failures (not from this expansion):** dirty-tree WIP around `semantic_similarity_v2` config/schema and config ownership/delegation goldens (registry counts, slice defaults, pydantic bridge). None of the failures are in the LLM response-parsing slice above.
- **Production code in this #tests pass:** none (only tests + assessment). Prior turn already landed coercion in `action_items_contract.py` / `llm_action_items.py`.
- **Quarantined tests:** not re-enabled.

---

## 72. Expansion (2026-07-24) – voice matching persistence

### Trigger
`/tests voice matching`

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260724-1008.zip` (5.7M); `custom-commands/` mirrored.
- **Collection (default filter):** `7528/7708` selected (`180` deselected) after this expansion.
- **Baseline before expansion:** `7492 passed, 1 failed, 2 skipped, 180 deselected`.
  - Sole failure then: `test_parse_action_items_drops_invalid_status` (LLM WIP drift; classified unrelated).
- **Cleanup:** disabled (per command).
- **Quarantined:** `0` active (`tests/quarantine/COUNT` = 0); not re-enabled.
- **Markers / addopts:** unchanged.
- **Voice contracts already present:** stages 0–9, bootstrap, operator, eval harness, finalize, chunked crash, audit fixes, completion (~80 tests). One skip when SpeechBrain is installed.

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| Speakers inventory UI helper | `list_samples_for_profile` untested | Filter + corrupt-skip contract |
| Per-profile wipe | Global wipe covered; `wipe_profile_voice` not | Dual-profile wipe leaves other + privacy |
| Export exclude prefixes | `./voice/...` thinner | Normalize-prefix contract |
| `ensure_data_dirs` voice layout | New dirs after persistence fix untested | Unit under `TestEnsureDataDirs` |
| Docker rebuild persistence | Implicit only | Compose bind-mount contract |
| Settings revoke UX | Confirm checkbox + bind-mount caption | Knob source contracts |

### Tests added / extended
| File | Change | Focus |
|------|--------|-------|
| `tests/contracts/test_speaker_profiles_voice_persistence.py` | **new (+4)** | inventory, export exclude, profile wipe isolation, empty wipe noop |
| `tests/core/utils/test_path_settings.py` | **+1** | `ensure_data_dirs` creates voice layout dirs |
| `tests/contracts/test_playwright_container_contracts.py` | **+1** | `./data:/data` + no speaker_profiles named volume |
| `tests/web/test_knobs_heavy_gui_contracts.py` | **+needles** | revoke confirm, bind-mount / rebuild captions |

### Validation
- Focused voice persistence + related knobs/layout: **9 passed**.
- Full voice contract slice (`test_speaker_profiles_voice*.py` + layout/compose): **86 passed, 1 skipped**.
- Default suite after expansion (dirty tree): **7484 passed, 30 failed, 2 skipped, 180 deselected**.
- **Unrelated failures:** config ownership/delegation goldens + `semantic_similarity_v2` WIP (`pilot_keys` expected 682 vs live registry), plus prior LLM parse drift. Voice matching slice green in isolation.
- **Production code from preceding persistence fix covered here:** `paths.ensure_data_dirs` voice layout, Speakers/Settings captions + revoke confirm, `docs/runtime/{docker,STORAGE}.md`.
- **Quarantined tests:** not re-enabled.

---

## 69. Expansion (2026-07-24) – Speaker profile page calculations

### Trigger
`/tests speaker profile page calculations` after Interactions/equity + Sentiment Speakers-detail packs.

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260724-1120.zip` (5.8M).
- **Cleanup:** disabled (per command).
- **Collection (default filter):** `7558/7738` selected (`180` deselected).
- **Baseline before expansion:** `7555 passed, 1 failed, 2 skipped, 180 deselected`.
- **Unrelated failure (classified, not fixed):** `tests/unit/test_audit_guardrails.py::test_analysis_modules_do_not_access_env_or_repos` flags `src/transcriptx/core/analysis/keyphrases/optional_methods.py` — outside speaker-profile packs.
- **Quarantined:** `0` active (`tests/quarantine/COUNT` = 0); not re-enabled.
- **Markers / addopts:** unchanged (excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow).
- **Structure:** `tests/{analysis,app,contracts,core,integration,io,optional,packaging,pipeline,presentation,quarantine,regression,release,scripts,services,smoke,unit,utils,web}`.
- **Focused calc baseline:** locations + interactions + sentiment + longitudinal + phase15*: **52 → 76 passed** after expansion (includes new join helpers).

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| Interactions pack totals/means | Single-appearance only | Two-appearance sum + mean dominance/floor |
| Newest-run selection | Implicit | Explicit mtime prefers `run-new` |
| Eligibility gate | Untested for pack | `needs_review` excluded from headline |
| Sentiment headline compound | Risk of mean-of-means | Weighted by `segment_count` ≠ 0.5 |
| Rows vs summary preference | Untested | Prefer segment rows; ignore `_with_sentiment` |
| Ignored links | Untested for sentiment | `include_ignored` toggles empty→ok |
| `run_artifact_join` | New shared helpers untested | `pick_speaker_entry` + `newest_run_with` |
| Speakers page wiring | Trends-only source contract | Interactions & Sentiment expanders + builders |

### Tests added / extended

| File | Change | Focus |
|------|--------|-------|
| `tests/unit/test_speaker_profile_interactions_pack.py` | **+3** | Multi-appearance sums/means, newest run, needs_review exclusion |
| `tests/unit/test_speaker_profile_sentiment_pack.py` | **+3** | Weighted compound, rows-over-summary, ignored eligibility |
| `tests/unit/test_speaker_profile_run_artifact_join.py` | **new (+2)** | Casefold pick + newest-run mtime |
| `tests/contracts/test_speaker_profiles_longitudinal.py` | **extended** | Page has Interactions & equity / Sentiment UI |

### Validation
- Focused speaker-profile calc slice: **76 passed**.
- Default suite after expansion (dirty tree): **7536 passed, 32 failed, 2 skipped, 181 deselected**.
- **Speaker-profile calc tests:** all green in the default run; no failures under `test_speaker_profile_*` / longitudinal page wiring.
- **Unrelated failures (dirty tree / WIP):** config ownership + pydantic pilot goldens, module-registry snapshot contracts, LLM presentation heading/footer strip, module UI group pin order, plus prior `audit_guardrails` keyphrases env access. Outside this expansion scope — not fixed here.
- **Production code in this #tests pass:** none (tests-only expansion; packs landed in prior agent turn).
- **Quarantined tests:** not re-enabled.

---

## GUI core pages coverage (# tests, 2026-07-24)

### Review
- Default fast suite baseline: **7612 passed**, 2 skipped, 188 deselected (green).
- Collected default: **7614/7802** (188 deselected by markers including `gui_acceptance`).
- Quarantined marker collect: **0 selected** under `-m quarantined` (no active quarantined collection in this env).
- Cleanup: disabled (per command).

### Gap (GUI core pages)
- Speakers page had methodology helpers only — **no** `render_speakers_page` L3 glue (directory empty / listing / detail).
- Home, Library, Import, Overview, Insights, Charts, Groups, Artifacts already had L3 page tests; seven AppTest journeys live under `tests/web/gui_acceptance/` (heavy).

### Expansion (tests-only)
| File | Change | Focus |
|------|--------|-------|
| `tests/web/test_speakers_page.py` | **new (+6)** | Empty state; incomplete snapshot warning + Active metric; archived-only filter clears selection; browser fragment → detail; missing profile error; surname sort |

### Validation
- `pytest -q tests/web/test_speakers_page.py` → **6 passed**.
- Streamlit assessment matrix updated for Speakers / Groups / Insights / Overview / Charts.
- Production code: **none**.
- Quarantined tests: **not re-enabled**.

---

## 73. Expansion (2026-07-24) – loader + atomic JSON + validation edges

### Trigger
`/tests` (full suite review + targeted expansion)

### Review
- **Backup:** `/Users/89298/Documents/transcriptx backup/260724-1539.zip` (5.9M); `custom-commands/` mirrored.
- **Collection (default filter):** `7608/7796` selected (`188` deselected) before expansion; full `-m ""` = `7796`.
- **Baseline before expansion:** `7605 passed, 1 failed, 2 skipped, 188 deselected`.
  - Sole failure: `test_stale_refs_script_exits_zero` — WIP `docs/dev/docs_architecture_1_0.md` quoted the denylist literal `readthedocs.io`. Classified as docs self-reference, not core suite health. Rephrased hostname wording (docs-only).
- **Cleanup:** disabled (per command).
- **Quarantined:** `0` active (`tests/quarantine/COUNT` = 0; `-m quarantined` selects nothing); not re-enabled.
- **Markers / addopts:** unchanged (excludes quarantined/smoke/release_only/integration*/requires_*/slow/legacy/semantic_v2_slow/gui_acceptance).
- **Structure:** `tests/{analysis,app,contracts,core,integration,io,optional,packaging,pipeline,presentation,quarantine,regression,release,scripts,services,smoke,unit,utils,web}`.
- **Targeted coverage (core/pipeline/contracts slice):** ~57% overall; high-leverage gaps called out: `io/transcript_loader` (~50% in that slice), `io/atomic_json` (no dedicated unit file).

### Coverage gaps targeted
| Area | Gap | Action |
|------|-----|--------|
| `load_segments` / `load_transcript` | Non-`.json`, non-list `segments`, path-resolution success, enriched JSONDecodeError | Extended `tests/io/test_transcript_loader.py` |
| `load_canonical_transcript` | No default-lane unit coverage (only integration mocks) | Happy path + empty raises |
| `atomic_json` | Shared crash-safe write primitive only covered incidentally | New `tests/io/test_atomic_json.py` |
| `validate_transcript_file` | High-leverage file only covered empty-path | Missing / non-JSON / valid v1 accept |

### Tests added / extended
| File | Change | Focus |
|------|--------|-------|
| `tests/io/test_transcript_loader.py` | **+8** | suffix gates, segments type, resolve_file_path, canonical loader, decode snippet |
| `tests/io/test_atomic_json.py` | **new (+11)** | strict dumps rejects; atomic write/replace/locked roundtrips |
| `tests/unit/test_high_leverage.py` | **+3** | validate_transcript_file missing / non-json / accept v1 |
| `docs/dev/docs_architecture_1_0.md` | wording | remove denylist self-hit for stale_refs |

### Validation
- Focused slice: **55 passed**.
- Default suite after expansion: **7628 passed, 2 skipped, 188 deselected**.
- **Production code:** none (tests + one docs hygiene rephrase).
- **Quarantined tests:** not re-enabled.
