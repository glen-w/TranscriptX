"""Display behaviour verification after Pydantic config migration."""

from __future__ import annotations

import pytest

from transcriptx.core.utils.config import (
    TranscriptXConfig,
    set_config,
    reset_config_for_tests,
)
from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env
from transcriptx.io.metadata_display_options import DurationDisplayOptions
from transcriptx.io.transcript_schema import compute_metadata_from_segments
from transcriptx.utils import text_utils as tu


def test_format_duration_display_from_config_minutes_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "transcriptx.io.metadata_display_options.get_duration_display_options",
        lambda: DurationDisplayOptions(
            hours_threshold_seconds=3600,
            style="minutes_only",
        ),
    )
    large_seconds = 8917 * 60
    assert tu.format_duration_display_from_config(large_seconds) == "8917m"


def test_format_duration_display_from_config_compact_default() -> None:
    assert tu.format_duration_display_from_config(62 * 60) == "1h 2m"


def test_metadata_duration_calculation_span_via_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRANSCRIPTX_METADATA_DURATION_CALCULATION", "span")
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.metadata.duration_calculation == "span"
    set_config(cfg)
    segments = [
        {"start": 5.0, "end": 20.0, "text": "hello"},
        {"start": 10.0, "end": 15.0, "text": "world"},
    ]
    meta = compute_metadata_from_segments(segments)
    assert meta.duration_seconds == 15.0
    monkeypatch.delenv("TRANSCRIPTX_METADATA_DURATION_CALCULATION", raising=False)
    reset_config_for_tests()


def test_metadata_duration_calculation_max_end_default() -> None:
    segments = [
        {"start": 10.0, "end": 20.0, "text": "hello"},
        {"start": 0.0, "end": 5.0, "text": "world"},
    ]
    meta = compute_metadata_from_segments(segments)
    assert meta.duration_seconds == 20.0


def test_dashboard_display_invalid_threshold_validation() -> None:
    from transcriptx.core.config import validate_config

    errors = validate_config({"dashboard": {"duration_hours_threshold_seconds": 0}})
    assert "dashboard.duration_hours_threshold_seconds" in errors
