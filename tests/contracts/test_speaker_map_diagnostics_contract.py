"""Contract tests for speaker_map_diagnostics (B19)."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.speaker_map_diagnostics.analyze import (
    SCHEMA_VERSION,
    SEMANTIC_VERSION,
    compute_speaker_map_diagnostics,
)

pytestmark = pytest.mark.contract


def test_unnamed_placeholder_is_t0() -> None:
    payload = compute_speaker_map_diagnostics(
        [{"speaker": "SPEAKER_00", "text": "hello"}],
        speaker_map={"SPEAKER_00": "SPEAKER_00"},
        has_sidecar=True,
    )
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["semantic_version"] == SEMANTIC_VERSION
    assert payload["speaker_tier"] == "T0"
    assert payload["named_speaker_count"] == 0
    assert "SPEAKER_00" in payload["unnamed_labels"]
    assert "quality_score" not in payload


def test_named_map_is_t3() -> None:
    payload = compute_speaker_map_diagnostics(
        [{"speaker": "SPEAKER_00", "text": "hello"}],
        speaker_map={"SPEAKER_00": "Alice"},
        has_sidecar=True,
    )
    assert payload["speaker_tier"] == "T3"
    assert payload["named_speaker_count"] == 1
    assert payload["status"] in {"ok", "partial"}


def test_empty_segments_absent() -> None:
    payload = compute_speaker_map_diagnostics([])
    assert payload["status"] == "absent"
    assert payload["unique_label_count"] == 0
