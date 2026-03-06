"""Tests for config validator dashboard checks."""

from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config_validator import ConfigValidator


def test_validator_rejects_invalid_overview_charts():
    config = TranscriptXConfig()
    config.dashboard.overview_charts = ["invalid.chart"]
    result = ConfigValidator().validate(config)
    assert result.is_valid is False
    assert any(error.field == "dashboard.overview_charts" for error in result.errors)


def test_validator_rejects_invalid_missing_behavior():
    config = TranscriptXConfig()
    config.dashboard.overview_missing_behavior = "unknown"
    result = ConfigValidator().validate(config)
    assert result.is_valid is False
    assert any(
        error.field == "dashboard.overview_missing_behavior" for error in result.errors
    )


def test_validator_rejects_invalid_max_items():
    config = TranscriptXConfig()
    config.dashboard.overview_max_items = -1
    result = ConfigValidator().validate(config)
    assert result.is_valid is False
    assert any(error.field == "dashboard.overview_max_items" for error in result.errors)
