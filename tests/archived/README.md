# Archived Tests

This directory is reserved for archiving unused or deprecated tests. Currently, most deprecated tests have already been removed from the codebase.

- **test_convokit.py** — archived with the ConvoKit analysis module (see [docs/ROADMAP.md](../../docs/ROADMAP.md) and [archived/convokit/](../../archived/convokit/)). These tests reference the archived ConvoKit implementation and will not run until the module is restored.

## Test Cleanup History

### Removed Tests (Already Deleted)

The following test files were removed as part of project cleanup:

#### Web Viewer Tests (Removed with web viewer feature)
- `tests/integration/test_web_integration.py` - Web viewer integration tests
- `tests/unit/test_web_viewer.py` - Web viewer unit tests

#### Deprecated Module Tests
- Tests for deprecated `io_utils` module functionality (migrated to `io` module)
- Tests for removed pipeline implementations

#### Other Removed Tests
- `tests/integration/test_cli_error_handling.py`
- `tests/integration/test_comprehensive_outputs.py`
- `tests/integration/test_consistency_standards.py`
- `tests/integration/test_cross_session_tracking.py`
- `tests/integration/test_performance_and_scalability.py`
- `tests/integration/test_security_and_validation.py`
- `tests/integration/test_semantic_advanced_integration.py`
- `tests/integration/test_semantic_optimization.py`
- `tests/integration/test_topic_modeling.py`
- `tests/root_tests/test_dag_integration.py`
- `tests/root_tests/test_dag_pipeline.py`
- `tests/root_tests/test_database_basic.py`
- `tests/root_tests/test_database_cli.py`
- `tests/root_tests/test_database_setup.py`
- `tests/root_tests/test_enhanced_topic_modeling.py`
- `tests/root_tests/test_folder_defaults.py`
- `tests/root_tests/test_module_inclusion.py`
- `tests/root_tests/test_ner_html.py`
- `tests/root_tests/test_preprocess_topic_modeling.py`
- `tests/root_tests/test_speaker_filtering_comprehensive.py`
- `tests/root_tests/test_speaker_map_fix.py`
- `tests/unit/test_acts_minimal.py`
- `tests/unit/test_analysis_utils.py`
- `tests/unit/test_basic_functionality.py`
- `tests/unit/test_both_methods.py`
- `tests/unit/test_clean_code_improvements.py`
- `tests/unit/test_config.py`
- `tests/unit/test_config_edit_utils.py`
- `tests/unit/test_core_modules.py`
- `tests/unit/test_core_utils.py`
- `tests/unit/test_database_integration.py`
- `tests/unit/test_display_utils.py`
- `tests/unit/test_file_selection_utils.py`
- `tests/unit/test_import_transcriptx.py`
- `tests/unit/test_io_ui.py`
- `tests/unit/test_io_utils.py`
- `tests/unit/test_ml_acts_fix.py`
- `tests/unit/test_ml_acts_simple.py`
- `tests/unit/test_module_selection.py`
- `tests/unit/test_semantic_advanced.py`
- `tests/unit/test_simple_acts.py`
- `tests/unit/test_simplify_transcript.py`
- `tests/unit/test_topic_minimal.py`
- `tests/unit/test_transcription_utils.py`
- `tests/unit/test_utils.py`
- `tests/unit/test_viewer_integration.py`
- `tests/unit/test_web_viewer.py`
- `tests/unit/test_with_numpy_fix.py`

## Current Active Test Structure

The current test suite is organized as follows:

### `tests/unit/` - Unit Tests
- `cli/` - CLI unit tests
- `core/` - Core functionality unit tests
  - `analysis/` - Analysis module tests
  - `data_extraction/` - Data extraction tests
  - `pipeline/` - Pipeline tests
  - `utils/` - Utility function tests
- `database/` - Database operation tests
- `io/` - I/O operation tests
- `utils/` - Utility tests

### `tests/integration/` - Integration Tests
- End-to-end workflow tests
- Cross-module integration tests
- Real-world scenario tests

### `tests/fixtures/` - Test Fixtures
- Shared test data and fixtures

### `tests/utils/` - Test Utilities
- Test helper functions and utilities

## Migration Notes

### io_utils → io Module Migration
Tests for `io_utils` functionality have been migrated to test the new `io` module. The old `io_utils` tests were removed as part of the module migration.

### Web Viewer Removal
All web viewer tests were removed when the web viewer feature was removed from the project. The project now focuses on CLI-based interaction.

## Restoration

If you need to restore any archived tests:
1. Verify the feature/functionality still exists in the codebase
2. Update test imports to match current module structure
3. Update test assertions to match current API
4. Run tests to ensure they pass with current codebase
5. Consider if functionality should be re-implemented rather than restoring old tests

## Date Archived

Most tests were removed during project cleanup on 2024-12-19.
