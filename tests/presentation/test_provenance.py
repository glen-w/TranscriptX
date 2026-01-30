"""Tests for provenance helpers."""

from __future__ import annotations

from transcriptx.core.presentation.provenance import (
    build_md_provenance,
    render_provenance_footer_md,
)


def test_build_md_provenance_dedupes_and_flags() -> None:
    payload = {
        "inputs": {"used_sentiment": True, "used_emotion": False},
        "provenance": {
            "input_source": "file_json",
            "segment_count": 12,
            "speaker_count_named": 2,
            "speaker_count_total": 3,
        },
        "modules": {
            "sentiment": {"status": "ok"},
            "emotion": {"status": "missing_input"},
        },
    }
    prov = build_md_provenance("summary", payload=payload)
    assert "sentiment" in prov["used"]
    assert "emotion" in prov["missing"]
    assert prov["input_source"] == "file_json"
    assert prov["segments"] == 12
    assert prov["speakers"] == "2/3"


def test_render_provenance_footer_md() -> None:
    footer = render_provenance_footer_md(
        {"used": ["sentiment"], "missing": ["emotion"], "segments": 5}
    )
    assert "Provenance" in footer
    assert "Used: sentiment" in footer
    assert "Missing: emotion" in footer
