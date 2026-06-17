"""Unit tests for ``core.utils.config_validator`` section/path checks.

Offline and deterministic. The per-section validators use ``hasattr``/``getattr``,
so lightweight ``SimpleNamespace`` configs precisely exercise each error/warning
branch without constructing a full ``TranscriptXConfig``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.core.utils.config_validator import (
    ConfigValidator,
    ValidationError,
    ValidationResult,
    validate_config,
    validate_config_and_raise,
)


@pytest.mark.unit
class TestValidationResultAndError:
    def test_error_str_format(self):
        err = ValidationError("a.b", "boom")
        assert str(err) == "ERROR: a.b: boom"

    def test_warning_str_format(self):
        err = ValidationError("a.b", "careful", severity="warning")
        assert str(err) == "WARNING: a.b: careful"

    def test_add_error_marks_invalid(self):
        result = ValidationResult()
        assert result.is_valid is True
        result.add_error("f", "m")
        assert result.is_valid is False
        assert result.errors and result.errors[0].severity == "error"

    def test_add_warning_keeps_valid(self):
        result = ValidationResult()
        result.add_warning("f", "m")
        assert result.is_valid is True
        assert result.warnings and result.warnings[0].severity == "warning"

    def test_get_all_issues_combines(self):
        result = ValidationResult()
        result.add_error("e", "1")
        result.add_warning("w", "2")
        issues = result.get_all_issues()
        assert len(issues) == 2
        assert {i.field for i in issues} == {"e", "w"}


@pytest.mark.unit
class TestValidateOutputConfig:
    def _validate(self, output):
        validator = ConfigValidator()
        result = ValidationResult()
        validator._validate_output_config(SimpleNamespace(output=output), result)
        return result

    def test_no_output_attr_is_noop(self):
        validator = ConfigValidator()
        result = ValidationResult()
        validator._validate_output_config(SimpleNamespace(), result)
        assert result.is_valid is True
        assert not result.get_all_issues()

    def test_missing_parent_dir_is_error(self, tmp_path: Path):
        missing = tmp_path / "does_not_exist" / "outputs"
        result = self._validate(SimpleNamespace(base_output_dir=str(missing)))
        assert result.is_valid is False
        assert any(e.field == "output.base_output_dir" for e in result.errors)

    def test_existing_parent_missing_dir_is_warning(self, tmp_path: Path):
        target = tmp_path / "outputs"  # parent (tmp_path) exists, dir does not
        result = self._validate(SimpleNamespace(base_output_dir=str(target)))
        assert result.is_valid is True
        assert any(w.field == "output.base_output_dir" for w in result.warnings)

    def test_non_bool_create_subdirectories_is_error(self, tmp_path: Path):
        result = self._validate(
            SimpleNamespace(base_output_dir="", create_subdirectories="yes")
        )
        assert result.is_valid is False
        assert any(e.field == "output.create_subdirectories" for e in result.errors)


@pytest.mark.unit
class TestValidateAnalysisConfig:
    def _validate(self, analysis):
        validator = ConfigValidator()
        result = ValidationResult()
        validator._validate_analysis_config(SimpleNamespace(analysis=analysis), result)
        return result

    def test_non_positive_timeout_is_error(self):
        result = self._validate(SimpleNamespace(timeout_seconds=0))
        assert any(e.field == "analysis.timeout_seconds" for e in result.errors)

    def test_invalid_max_workers_is_error(self):
        result = self._validate(SimpleNamespace(timeout_seconds=10, max_workers=0))
        assert any(e.field == "analysis.max_workers" for e in result.errors)

    def test_valid_analysis_has_no_errors(self):
        result = self._validate(SimpleNamespace(timeout_seconds=30.0, max_workers=4))
        assert result.is_valid is True


@pytest.mark.unit
class TestValidateLoggingConfig:
    def _validate(self, logging):
        validator = ConfigValidator()
        result = ValidationResult()
        validator._validate_logging_config(SimpleNamespace(logging=logging), result)
        return result

    def test_invalid_level_is_error(self):
        result = self._validate(SimpleNamespace(level="VERBOSE", file=None))
        assert any(e.field == "logging.level" for e in result.errors)

    def test_missing_log_dir_is_error(self, tmp_path: Path):
        bad_file = tmp_path / "no_such_dir" / "tx.log"
        result = self._validate(SimpleNamespace(level="INFO", file=str(bad_file)))
        assert any(e.field == "logging.file" for e in result.errors)

    def test_valid_logging_has_no_errors(self, tmp_path: Path):
        ok_file = tmp_path / "tx.log"
        result = self._validate(SimpleNamespace(level="DEBUG", file=str(ok_file)))
        assert result.is_valid is True


@pytest.mark.unit
class TestValidatePaths:
    def test_import_failure_records_warning(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "transcriptx.core.utils.paths":
                raise ImportError("simulated")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        validator = ConfigValidator()
        result = ValidationResult()
        validator._validate_paths(SimpleNamespace(), result)
        assert any(w.field == "paths" for w in result.warnings)


@pytest.mark.unit
class TestPublicEntrypoints:
    def test_validate_config_and_raise_raises_on_invalid(self):
        bad = SimpleNamespace(analysis=SimpleNamespace(max_workers=0))
        with pytest.raises(ValueError, match="Configuration validation failed"):
            validate_config_and_raise(bad)

    def test_validate_config_and_raise_logs_warnings_without_raising(self, tmp_path):
        # Only a warning (missing output dir whose parent exists) -> still valid.
        cfg = SimpleNamespace(
            output=SimpleNamespace(base_output_dir=str(tmp_path / "outputs"))
        )
        validate_config_and_raise(cfg)  # must not raise

    def test_validate_config_uses_default_when_none(self):
        result = validate_config(None)
        assert isinstance(result, ValidationResult)
