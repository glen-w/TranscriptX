"""Tests for segments timestamp."""

from __future__ import annotations

from transcriptx.web.transcript_viewer.segments import _format_timestamp_range


def test_format_timestamp_range_seconds() -> None:
    assert _format_timestamp_range(1.2, 3.4, "seconds") == "1.2s - 3.4s"


def test_format_timestamp_range_seconds_uses_mmss_after_sixty() -> None:
    assert _format_timestamp_range(914.1, 950.4, "seconds") == "15:14 - 15:50"


def test_safe_display_timestamp_range_tolerates_invalid() -> None:
    from transcriptx.web.transcript_viewer.segments import _safe_display_timestamp_range

    assert _safe_display_timestamp_range(1.2, 3.4, "seconds") == "1.2s - 3.4s"
    assert _safe_display_timestamp_range(None, 3.4, "seconds") is None
    assert _safe_display_timestamp_range("bad", 3.4, "seconds") is None
