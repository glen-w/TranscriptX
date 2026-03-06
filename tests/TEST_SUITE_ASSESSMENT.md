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
