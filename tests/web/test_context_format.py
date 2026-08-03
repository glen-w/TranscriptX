"""Tests for pure context formatting helpers."""

from __future__ import annotations

from datetime import datetime

from transcriptx.web.context_format import (
    format_context_line,
    format_run_display,
    friendly_subject_label,
    parse_run_timestamp,
)


def test_friendly_transcript_slug_index_precedence():
    assert (
        friendly_subject_label(
            "transcript",
            subject_id="slug-a",
            slug_labels={"slug-a": "Suzanne interview"},
            display_name="ignored",
            stem="ignored",
        )
        == "Suzanne interview"
    )


def test_friendly_transcript_display_then_stem_then_id():
    assert (
        friendly_subject_label(
            "transcript",
            subject_id="slug-a",
            display_name="Display Name",
            stem="stem_name",
        )
        == "Display Name"
    )
    assert (
        friendly_subject_label(
            "transcript",
            subject_id="slug-a",
            stem="stem_name",
        )
        == "stem_name"
    )
    assert friendly_subject_label("transcript", subject_id="slug-a") == "slug-a"


def test_friendly_group_display_then_id():
    assert (
        friendly_subject_label("group", subject_id="g1", display_name="Team sync")
        == "Team sync"
    )
    assert friendly_subject_label("group", subject_id="g1") == "g1"


def test_friendly_empty_and_unknown():
    assert friendly_subject_label("transcript") == "No transcript"
    assert friendly_subject_label("group") == "No group"
    assert friendly_subject_label("Transcript") == "No subject"
    assert friendly_subject_label(None) == "No subject"
    assert friendly_subject_label("other") == "No subject"


def test_friendly_whitespace_and_unicode():
    assert (
        friendly_subject_label(
            "transcript",
            subject_id="s",
            display_name="  Café résumé  ",
        )
        == "Café résumé"
    )
    assert (
        friendly_subject_label(
            "transcript",
            subject_id="s",
            display_name="   ",
            stem="keep_underscores",
        )
        == "keep_underscores"
    )


def test_parse_run_timestamp_valid_and_invalid():
    dt = parse_run_timestamp("20260713_022448_09488448")
    assert dt == datetime(2026, 7, 13, 2, 24, 48)
    assert parse_run_timestamp("not-a-run") is None
    assert parse_run_timestamp("") is None
    assert parse_run_timestamp(None) is None
    assert parse_run_timestamp("20260713") is None


def test_format_run_display_no_raw_fallback():
    assert format_run_display("20260713_022448_09488448") == "Run 13 Jul 2026, 02:24"
    assert (
        format_run_display(
            "bad-id",
            fallback_dt=datetime(2026, 7, 13, 3, 29),
            allow_raw_fallback=False,
        )
        == "Run 13 Jul 2026, 03:29"
    )
    assert (
        format_run_display("opaque-run-id", allow_raw_fallback=False) == "Run selected"
    )
    assert format_run_display(None, allow_raw_fallback=False) == "No run"
    assert format_run_display("", allow_raw_fallback=False) == "No run"


def test_format_run_display_allow_raw_fallback():
    assert (
        format_run_display("opaque-run-id", allow_raw_fallback=True) == "opaque-run-id"
    )
    assert format_run_display(None, allow_raw_fallback=True) == "No run"


def test_format_context_line_no_type_token_or_raw_primary():
    presentation = format_context_line(
        subject_type="transcript",
        subject_label="Suzanne interview",
        run_id="20260713_022448_09488448",
    )
    assert presentation.primary_text == "Suzanne interview / Run 13 Jul 2026, 02:24"
    assert "Transcript" not in presentation.primary_text
    assert "20260713_022448_09488448" not in presentation.primary_text
    assert presentation.raw_run_id == "20260713_022448_09488448"
    assert "Full run identifier" in presentation.tooltip_label

    opaque = format_context_line(
        subject_type="group",
        subject_label="Team sync",
        run_id="opaque",
    )
    assert opaque.primary_text == "Team sync / Run selected"
    assert opaque.raw_run_id == "opaque"


def test_format_context_line_empty_when_nothing_selected():
    empty = format_context_line(
        subject_type="transcript",
        subject_label="No transcript",
        run_id=None,
    )
    assert empty.primary_text == ""
    assert empty.raw_run_id is None

    empty_group = format_context_line(
        subject_type="group",
        subject_label="No group",
    )
    assert empty_group.primary_text == ""

    # Partial empty still shows placeholders.
    subject_only = format_context_line(
        subject_type="transcript",
        subject_label="Suzanne",
        run_id=None,
    )
    assert subject_only.primary_text == "Suzanne / No run"
