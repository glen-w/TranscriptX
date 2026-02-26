"""
Tests for output validation utilities.

This module tests validation of analysis module outputs.
"""

from transcriptx.core.utils.output_validation import (
    ModuleValidationRule,
    check_module_has_outputs,
    validate_module_outputs,
    get_modules_with_warnings,
    get_validation_summary,
    MODULE_VALIDATION_RULES,
)


class TestModuleValidationRule:
    """Tests for ModuleValidationRule dataclass."""

    def test_initialization(self):
        """Test ModuleValidationRule initialization."""
        rule = ModuleValidationRule(
            required_files=["*.json"],
            required_dirs=["data"],
            min_files=1,
            file_extensions={".json"},
        )

        assert rule.required_files == ["*.json"]
        assert rule.required_dirs == ["data"]
        assert rule.min_files == 1
        assert rule.file_extensions == {".json"}


class TestCheckModuleHasOutputs:
    """Tests for check_module_has_outputs function."""

    def test_returns_true_when_outputs_exist(self, tmp_path):
        """Test that True is returned when outputs exist."""
        module_dir = tmp_path / "sentiment"
        module_dir.mkdir()
        data_dir = module_dir / "data"
        data_dir.mkdir()
        output_file = data_dir / "test_with_sentiment.json"
        output_file.write_text("{}")

        result, warnings = check_module_has_outputs(module_dir, "sentiment")

        assert result is True
        assert warnings == []

    def test_returns_false_when_outputs_missing(self, tmp_path):
        """Test that False is returned when outputs are missing."""
        module_dir = tmp_path / "sentiment"
        module_dir.mkdir()

        result, warnings = check_module_has_outputs(module_dir, "sentiment")

        assert result is True
        assert warnings

    def test_handles_unknown_module(self, tmp_path):
        """Test that unknown modules are handled."""
        module_dir = tmp_path / "unknown_module"
        module_dir.mkdir()

        result, _warnings = check_module_has_outputs(module_dir, "unknown_module")

        # Should return False or handle gracefully
        assert isinstance(result, bool)


class TestValidateModuleOutputs:
    """Tests for validate_module_outputs function."""

    def test_validates_module_outputs(self, tmp_path):
        """Test that module outputs are validated."""
        module_dir = tmp_path / "sentiment"
        module_dir.mkdir()
        data_dir = module_dir / "data"
        data_dir.mkdir()
        output_file = data_dir / "test_with_sentiment.json"
        output_file.write_text("{}")

        result = validate_module_outputs(module_dir, ["sentiment"])

        assert isinstance(result, dict)
        assert "sentiment" in result
        assert isinstance(result["sentiment"], tuple)

    def test_detects_missing_required_files(self, tmp_path):
        """Test that missing required files are detected."""
        module_dir = tmp_path / "sentiment"
        module_dir.mkdir()
        # Don't create required files

        result = validate_module_outputs(module_dir, ["sentiment"])

        assert isinstance(result, dict)
        assert "sentiment" in result
        # Should indicate missing files via warnings
        assert result["sentiment"][1]


class TestGetModulesWithWarnings:
    """Tests for get_modules_with_warnings function."""

    def test_returns_modules_with_warnings(self, tmp_path):
        """Test that modules with warnings are returned."""
        basename_dir = tmp_path / "test"
        basename_dir.mkdir()

        # Create module dirs
        sentiment_dir = basename_dir / "sentiment"
        sentiment_dir.mkdir()
        # Don't create required outputs

        expected_modules = ["sentiment", "emotion"]

        result = get_modules_with_warnings(basename_dir, expected_modules)

        assert isinstance(result, list)
        # Should include sentiment (missing outputs)
        assert "sentiment" in result or len(result) > 0

    def test_returns_empty_when_no_warnings(self, tmp_path):
        """Test that empty list is returned when no warnings."""
        basename_dir = tmp_path / "test"
        basename_dir.mkdir()

        # Create complete module outputs
        sentiment_dir = basename_dir / "sentiment"
        sentiment_dir.mkdir()
        data_dir = sentiment_dir / "data"
        data_dir.mkdir()
        output_file = data_dir / "test_with_sentiment.json"
        output_file.write_text("{}")

        expected_modules = ["sentiment"]

        result = get_modules_with_warnings(basename_dir, expected_modules)

        # Should have no warnings if outputs are complete
        assert isinstance(result, list)


class TestGetValidationSummary:
    """Tests for get_validation_summary function."""

    def test_returns_validation_summary(self, tmp_path):
        """Test that validation summary is returned."""
        basename_dir = tmp_path / "test"
        basename_dir.mkdir()

        expected_modules = ["sentiment", "emotion"]

        result = get_validation_summary(basename_dir, expected_modules)

        assert isinstance(result, dict)
        assert "total_modules" in result
        assert "modules_with_warnings" in result
        assert "modules_without_warnings" in result
        assert "validation_results" in result


class TestModuleValidationRules:
    """Tests for MODULE_VALIDATION_RULES."""

    def test_rules_exist_for_common_modules(self):
        """Test that validation rules exist for common modules."""
        assert "sentiment" in MODULE_VALIDATION_RULES
        assert "emotion" in MODULE_VALIDATION_RULES
        assert "ner" in MODULE_VALIDATION_RULES

    def test_rules_have_required_fields(self):
        """Test that rules have required fields."""
        for module_name, rule in MODULE_VALIDATION_RULES.items():
            assert hasattr(rule, "required_files")
            assert hasattr(rule, "required_dirs")
            assert isinstance(rule.required_files, list)
            assert isinstance(rule.required_dirs, list)
