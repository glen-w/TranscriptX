"""Tests for shared dropdown option formatter helpers."""

from types import SimpleNamespace

import pytest

import transcriptx.web.module_option_format as module_option_format
from transcriptx.web.module_option_format import format_module_option
from transcriptx.web.transcript_option_format import (
    format_transcript_option_with_analysis_status,
    format_transcript_option_with_speaker_status,
)


def test_format_module_option_uses_group_title_for_known_module() -> None:
    formatted = format_module_option("stats", label_builder=lambda _: "Stats")
    assert formatted == "Foundations · Stats"


def test_format_module_option_uses_other_bucket_for_unknown_module() -> None:
    formatted = format_module_option(
        "module_does_not_exist", label_builder=lambda _: "X"
    )
    assert formatted == "Other · X"


def test_format_transcript_option_with_analysis_status() -> None:
    assert (
        format_transcript_option_with_analysis_status("Meeting", "no analysis")
        == "Meeting (no analysis)"
    )


def test_format_transcript_option_defaults_when_summary_missing_fields() -> None:
    label = format_transcript_option_with_speaker_status(SimpleNamespace())
    assert label == " (none, 0 segs)"


def test_format_transcript_option_partial_includes_speaker_counts() -> None:
    summary = SimpleNamespace(
        base_name="team_sync",
        speaker_map_status="partial",
        segment_count=12,
        unidentified_speaker_count=2,
        ignored_speaker_count=1,
    )
    label = format_transcript_option_with_speaker_status(summary)
    assert label == "team_sync (partial, 12 segs), 2 unidentified, 1 ignored"


def test_format_transcript_option_non_partial_omits_speaker_counts() -> None:
    summary = SimpleNamespace(
        base_name="retro",
        speaker_map_status="complete",
        segment_count=5,
        unidentified_speaker_count=9,
        ignored_speaker_count=9,
    )
    label = format_transcript_option_with_speaker_status(summary)
    assert label == "retro (complete, 5 segs)"


def test_format_module_option_uses_default_label_builder_when_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module_option_format,
        "build_module_label",
        lambda module_id: f"Label:{module_id}",
    )
    formatted = format_module_option("stats")
    assert formatted == "Foundations · Label:stats"


def test_build_module_label_marks_category_heavy() -> None:
    from transcriptx.web.module_registry import build_module_label

    # topic_modeling is category=heavy with cost_tier=normal
    label = build_module_label("topic_modeling")
    assert "heavy" in label


def test_format_transcript_option_partial_missing_counts_defaults_to_zero() -> None:
    summary = SimpleNamespace(
        base_name="daily_sync",
        speaker_map_status="partial",
        segment_count=7,
    )
    label = format_transcript_option_with_speaker_status(summary)
    assert label == "daily_sync (partial, 7 segs), 0 unidentified, 0 ignored"
