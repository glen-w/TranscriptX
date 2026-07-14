"""Unit tests for summary module resolve/render helpers (offline)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from transcriptx.core.analysis.summary import (
    _ensure_highlights_themes,
    _extract_transcript_file_id,
    _resolve_highlights,
    render_summary_markdown,
)
from transcriptx.core.utils.config.analysis import HighlightsConfig, SummaryConfig


def _config(
    *,
    require_highlights: bool = False,
    compute_if_missing: bool = False,
    allow_degraded: bool = True,
):
    # SummaryConfig fields are hydrated from SummarySettingsModel (init=False).
    summary = SummaryConfig()
    summary.require_highlights = require_highlights
    summary.compute_highlights_if_missing = compute_if_missing
    summary.allow_degraded = allow_degraded
    return SimpleNamespace(
        analysis=SimpleNamespace(summary=summary, highlights=HighlightsConfig())
    )


def test_ensure_highlights_themes_attaches_when_missing() -> None:
    highlights: dict = {"sections": {"cold_open": {"items": []}}}
    ctx = SimpleNamespace(get_transcript_key=lambda: "tk-1")
    with patch(
        "transcriptx.core.analysis.summary.attach_themes_to_highlights",
        side_effect=lambda h: h.__setitem__("themes", [{"label": "x"}]),
    ):
        _ensure_highlights_themes(highlights, ctx)
    assert highlights["transcript_key"] == "tk-1"
    assert "themes" in highlights
    _ensure_highlights_themes({}, ctx)  # no-op on empty


def test_resolve_highlights_from_context_artifact_computed_degraded_and_require(
    tmp_path: Path,
) -> None:
    ctx = SimpleNamespace(
        get_analysis_result=lambda _name: {"from": "context"},
        get_base_name=lambda: "base",
        get_transcript_dir=lambda: str(tmp_path),
        get_transcript_key=lambda: "tk",
    )
    payload, source = _resolve_highlights(ctx, [], _config())
    assert source == "context"
    assert payload["from"] == "context"

    ctx2 = SimpleNamespace(
        get_analysis_result=lambda _name: None,
        get_base_name=lambda: "base",
        get_transcript_dir=lambda: str(tmp_path),
        get_transcript_key=lambda: "tk",
    )
    art_dir = tmp_path / "highlights" / "data" / "global"
    art_dir.mkdir(parents=True)
    (art_dir / "base_highlights.json").write_text(
        json.dumps({"from": "artifact"}), encoding="utf-8"
    )
    payload, source = _resolve_highlights(ctx2, [], _config())
    assert source == "artifact"
    assert payload["from"] == "artifact"

    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    ctx3 = SimpleNamespace(
        get_analysis_result=lambda _name: None,
        get_base_name=lambda: "none",
        get_transcript_dir=lambda: str(empty_root),
        get_transcript_key=lambda: "tk",
    )
    with pytest.raises(ValueError, match="requires highlights"):
        _resolve_highlights(ctx3, [], _config(require_highlights=True))

    with (
        patch(
            "transcriptx.core.analysis.summary.compute_highlights",
            return_value={"sections": {}},
        ),
        patch(
            "transcriptx.core.analysis.summary.attach_themes_to_highlights",
            lambda h: None,
        ),
    ):
        payload, source = _resolve_highlights(
            ctx3, [], _config(compute_if_missing=True, allow_degraded=False)
        )
    assert source == "computed_by_summary"
    assert payload["transcript_key"] == "tk"

    payload, source = _resolve_highlights(ctx3, [], _config(allow_degraded=True))
    assert source == "missing"
    assert payload == {}

    with pytest.raises(ValueError, match="compute_highlights_if_missing"):
        _resolve_highlights(
            ctx3, [], _config(allow_degraded=False, compute_if_missing=False)
        )


def test_render_summary_markdown_no_signal_and_computed_note() -> None:
    empty = render_summary_markdown(
        {
            "inputs": {
                "highlights_source": "missing",
                "used_sentiment": False,
                "used_emotion": False,
                "used_highlights": False,
            },
            "overview": {"paragraph": ""},
            "key_themes": {"bullets": []},
            "tension_points": {"bullets": []},
            "commitments": {"items": []},
        }
    )
    assert "Executive Summary" in empty
    assert (
        "did not meet" in empty.lower()
        or "no signal" in empty.lower()
        or "thresholds" in empty.lower()
    )

    filled = render_summary_markdown(
        {
            "inputs": {
                "highlights_source": "computed_by_summary",
                "used_sentiment": True,
                "used_emotion": False,
                "used_highlights": True,
            },
            "overview": {"paragraph": "Session overview."},
            "key_themes": {"bullets": [{"text": "budget risk"}]},
            "tension_points": {
                "bullets": [
                    {
                        "text": "Tension",
                        "anchor_quote": {
                            "speaker": "Alice",
                            "quote": "No",
                            "start": 0.0,
                            "end": 1.0,
                            "segment_refs": {"segment_indexes": [0]},
                        },
                    }
                ]
            },
            "commitments": {"items": [{"owner_display": "Bob", "action": "will ship"}]},
        }
    )
    assert "budget risk" in filled
    assert "computed implicitly" in filled.lower()
    # Commitments render in Insights Actions, not executive summary markdown.
    assert "Bob" not in filled
    assert "will ship" not in filled


def test_extract_transcript_file_id_edges() -> None:
    assert _extract_transcript_file_id([]) is None
    assert _extract_transcript_file_id([{"transcript_file_id": "12"}]) == 12
    assert _extract_transcript_file_id([{"transcript_file_id": "bad"}]) is None
