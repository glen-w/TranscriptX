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
