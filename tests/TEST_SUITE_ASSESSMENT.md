# Pytest Suite Assessment

**Date:** 2026-02-02  
**Scope:** Assess suite, quarantine obsolete tests, add high-leverage unit and integration tests.

---

## 1. Suite overview

- **Collected:** ~1558 tests (3 skipped at collection for missing modules).
- **Structure:** `tests/analysis/`, `tests/cli/`, `tests/core/`, `tests/integration/`, `tests/io/`, `tests/pipeline/`, `tests/database/`, `tests/contracts/`, `tests/regression/`, `tests/smoke/`, `tests/unit/`, `tests/utils/`, etc.
- **Markers:** `smoke`, `unit`, `integration`, `contract`, `slow`, `requires_models`, `requires_docker`, `quarantined`, `integration_core`, `integration_extended`, etc.

---

## 2. Obsolete / irrelevant tests (quarantined)

The following CLI test **files** target APIs that were removed or renamed (e.g. `select_transcript_file_interactive`, `settings_menu_loop`, `load_processing_state`, `CrossSessionTrackingService`, `db_reset_command`). They are marked with `pytest.mark.quarantined` and **excluded from the default pytest run** so CI can stay green while the CLI stabilizes.

| File | Reason |
|------|--------|
| `tests/cli/test_analysis_workflow_impl.py` | Patches `select_transcript_file_interactive`, `generate_stats_from_file`, `validate_transcript_file` (no longer on module). |
| `tests/cli/test_config_editor.py` | Patches `settings_menu_loop` (no longer exists). |
| `tests/cli/test_cross_session_commands.py` | Tests `CrossSessionTrackingService`, `get_session` (removed/renamed). |
| `tests/cli/test_database_commands.py` | Module `transcriptx.database.db_reset_command` missing; CLI exit codes/args changed. |
| `tests/cli/test_batch_wav_workflow_impl.py` | Patches `load_processing_state`; state shape uses different keys (e.g. `processed_count`). |
| `tests/cli/test_file_selection.py` | Patches `select_transcript_file`, `select_audio_file`, etc. (moved/renamed). |
| `tests/cli/test_file_processor.py` | Patches `extract_tags_from_transcript` (no longer on module). |
| `tests/cli/test_tag_workflow.py` | Patches `extract_tags` (no longer on module). |
| `tests/cli/test_wav_processing_workflow_impl.py` | Patches `select_folder_interactive` (no longer on module). |
| `tests/cli/test_workflows.py` | Patches workflow entrypoints that were removed/renamed. |
| `tests/cli/test_main.py` | `app.commands`, `run_single_analysis_workflow`, exit codes changed. |
| `tests/cli/test_transcription_workflow_impl.py` | Patches `select_audio_file`, `validate_transcript_file`, `start_whisperx_compose_service`; API uses `target` not `transcript_path`. |

**Run including quarantined:**  
`pytest -m ""` or remove `-m "not quarantined"` from `pytest.ini` addopts.

**Run only quarantined:**  
`pytest -m quarantined`

---

## 3. Skipped at collection (missing modules)

- `tests/analysis/test_rules.py` – `transcriptx.core.analysis.rules` not found.
- `tests/cli/test_audio_playback.py`, `tests/cli/test_audio_utils.py` – `transcriptx.cli.audio_utils` not found.

These remain in the tree; fix or remove when the corresponding modules are (re)introduced or deprecated.

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
