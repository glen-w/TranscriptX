"""
Centralized configuration validation layer.

This module provides comprehensive validation for TranscriptX configuration,
ensuring that all settings are valid before use.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


@dataclass
class ValidationError:
    """A configuration validation error."""

    field: str
    message: str
    severity: str = "error"  # "error" or "warning"

    def __str__(self) -> str:
        return f"{self.severity.upper()}: {self.field}: {self.message}"


@dataclass
class ValidationResult:
    """Result of configuration validation."""

    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]

    def __init__(self):
        self.is_valid = True
        self.errors = []
        self.warnings = []

    def add_error(self, field: str, message: str) -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(field, message, "error"))
        self.is_valid = False

    def add_warning(self, field: str, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(ValidationError(field, message, "warning"))

    def get_all_issues(self) -> List[ValidationError]:
        """Get all errors and warnings."""
        return self.errors + self.warnings


class ConfigValidator:
    """
    Centralized configuration validator.

    This class provides comprehensive validation for TranscriptX configuration,
    checking all aspects of the configuration for validity.
    """

    def __init__(self):
        """Initialize the validator."""
        self.logger = get_logger()

    def validate(self, config: TranscriptXConfig) -> ValidationResult:
        """
        Validate a configuration object.

        Args:
            config: Configuration to validate

        Returns:
            ValidationResult with all errors and warnings
        """
        result = ValidationResult()

        # Validate each section
        self._validate_output_config(config, result)
        self._validate_analysis_config(config, result)
        self._validate_transcription_config(config, result)
        self._validate_logging_config(config, result)
        self._validate_dashboard_config(config, result)

        # Validate paths
        self._validate_paths(config, result)

        return result

    def _validate_dashboard_config(
        self, config: TranscriptXConfig, result: ValidationResult
    ) -> None:
        dashboard = getattr(config, "dashboard", None)
        if dashboard is None:
            return

        try:
            from transcriptx.core.utils.chart_registry import get_chart_registry

            registry = get_chart_registry()
            valid_viz_ids = set(registry.keys())
        except Exception:
            valid_viz_ids = set()

        invalid_ids = [
            str(viz_id)
            for viz_id in (dashboard.overview_charts or [])
            if str(viz_id) not in valid_viz_ids
        ]
        if invalid_ids:
            result.add_error(
                "dashboard.overview_charts",
                "Unknown chart IDs: " + ", ".join(invalid_ids),
            )

        missing_behavior = getattr(dashboard, "overview_missing_behavior", None)
        if missing_behavior not in ("skip", "show_placeholder"):
            result.add_error(
                "dashboard.overview_missing_behavior",
                "Value must be one of: skip, show_placeholder.",
            )

        max_items = getattr(dashboard, "overview_max_items", None)
        if max_items is not None:
            if not isinstance(max_items, int) or max_items <= 0:
                result.add_error(
                    "dashboard.overview_max_items",
                    "Value must be a positive integer or None.",
                )

    def _validate_output_config(
        self, config: TranscriptXConfig, result: ValidationResult
    ) -> None:
        """Validate output configuration."""
        if not hasattr(config, "output"):
            return

        output = config.output

        # Validate base output directory
        if hasattr(output, "base_output_dir") and output.base_output_dir:
            base_dir = Path(output.base_output_dir)
            if not base_dir.parent.exists():
                result.add_error(
                    "output.base_output_dir",
                    f"Parent directory does not exist: {base_dir.parent}",
                )
            elif not base_dir.exists():
                # Directory doesn't exist but parent does - this is OK, will be created
                result.add_warning(
                    "output.base_output_dir",
                    f"Output directory does not exist, will be created: {base_dir}",
                )

        # Validate create_subdirectories
        if hasattr(output, "create_subdirectories"):
            if not isinstance(output.create_subdirectories, bool):
                result.add_error(
                    "output.create_subdirectories", "Must be a boolean value"
                )

    def _validate_analysis_config(
        self, config: TranscriptXConfig, result: ValidationResult
    ) -> None:
        """Validate analysis configuration."""
        if not hasattr(config, "analysis"):
            return

        analysis = config.analysis

        # Validate timeout values
        if hasattr(analysis, "timeout_seconds"):
            if (
                not isinstance(analysis.timeout_seconds, (int, float))
                or analysis.timeout_seconds <= 0
            ):
                result.add_error(
                    "analysis.timeout_seconds", "Must be a positive number"
                )

        # Validate parallel execution settings
        if hasattr(analysis, "max_workers"):
            if not isinstance(analysis.max_workers, int) or analysis.max_workers < 1:
                result.add_error("analysis.max_workers", "Must be a positive integer")

    def _validate_transcription_config(
        self, config: TranscriptXConfig, result: ValidationResult
    ) -> None:
        """Validate transcription configuration."""
        if not hasattr(config, "transcription"):
            return

        transcription = config.transcription

        # Validate max_speakers
        if hasattr(transcription, "max_speakers"):
            if (
                not isinstance(transcription.max_speakers, int)
                or transcription.max_speakers < 1
            ):
                result.add_error(
                    "transcription.max_speakers", "Must be a positive integer"
                )

    def _validate_logging_config(
        self, config: TranscriptXConfig, result: ValidationResult
    ) -> None:
        """Validate logging configuration."""
        if not hasattr(config, "logging"):
            return

        logging = config.logging

        # Validate log level
        if hasattr(logging, "level"):
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if logging.level not in valid_levels:
                result.add_error(
                    "logging.level", f"Must be one of: {', '.join(valid_levels)}"
                )

        # Validate log file path if specified
        if hasattr(logging, "file") and logging.file:
            log_file = Path(logging.file)
            if not log_file.parent.exists():
                result.add_error(
                    "logging.file",
                    f"Log file directory does not exist: {log_file.parent}",
                )

    def _validate_paths(
        self, config: TranscriptXConfig, result: ValidationResult
    ) -> None:
        """Validate all path-related settings."""
        # Check that required directories can be created
        try:
            from transcriptx.core.utils.paths import OUTPUTS_DIR, DATA_DIR

            output_dir = Path(OUTPUTS_DIR)
            data_dir = Path(DATA_DIR)

            # Check parent directories exist
            if not output_dir.parent.exists():
                result.add_error(
                    "paths.outputs_dir",
                    f"Outputs directory parent does not exist: {output_dir.parent}",
                )

            if not data_dir.parent.exists():
                result.add_error(
                    "paths.data_dir",
                    f"Data directory parent does not exist: {data_dir.parent}",
                )
        except Exception as e:
            result.add_warning("paths", f"Could not validate paths: {e}")


def validate_config(config: Optional[TranscriptXConfig] = None) -> ValidationResult:
    """
    Validate configuration (convenience function).

    Args:
        config: Configuration to validate (default: get_config())

    Returns:
        ValidationResult with all errors and warnings
    """
    if config is None:
        from transcriptx.core.utils.config import get_config

        config = get_config()

    validator = ConfigValidator()
    return validator.validate(config)


def validate_config_and_raise(config: Optional[TranscriptXConfig] = None) -> None:
    """
    Validate configuration and raise exception if invalid.

    Args:
        config: Configuration to validate (default: get_config())

    Raises:
        ValueError: If configuration is invalid
    """
    result = validate_config(config)

    if not result.is_valid:
        error_messages = [str(error) for error in result.errors]
        raise ValueError(
            f"Configuration validation failed:\n" + "\n".join(error_messages)
        )

    # Log warnings
    if result.warnings:
        for warning in result.warnings:
            logger.warning(str(warning))
