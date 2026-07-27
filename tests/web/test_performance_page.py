"""Performance page presentation helpers."""

from __future__ import annotations

import pytest

from transcriptx.web.page_modules.performance import _format_metric_duration_ms


@pytest.mark.unit
def test_format_metric_duration_ms_under_one_minute() -> None:
    assert _format_metric_duration_ms(None) == "—"
    assert _format_metric_duration_ms(0.0) == "0.00s"
    assert _format_metric_duration_ms(1250.0) == "1.25s"
    assert _format_metric_duration_ms(59_990.0) == "59.99s"


@pytest.mark.unit
def test_format_metric_duration_ms_minutes_and_seconds() -> None:
    assert _format_metric_duration_ms(60_000.0) == "1m 0s"
    assert _format_metric_duration_ms(375_110.0) == "6m 15s"
    assert _format_metric_duration_ms(1_221_230.0) == "20m 21s"
    assert _format_metric_duration_ms(3_661_000.0) == "1h 1m 1s"
