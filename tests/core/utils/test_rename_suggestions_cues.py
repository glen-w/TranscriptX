"""Transcript cues and stem rendering for rename suggestions."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from transcriptx.core.utils.rename.smart_name import validate_smart_rename_pattern
from transcriptx.core.utils.rename.suggestions.models import RawRenameCue
from transcriptx.core.utils.rename.suggestions.render import render_stem_from_cue, slug_title
from transcriptx.core.utils.rename.suggestions.transcript_cues import (
    extract_title_from_text,
    extract_transcript_cues,
    looks_like_public_event,
    parse_date_from_text,
)


def test_parse_date_from_recorded_on_phrase() -> None:
    text = "This session was recorded on March 12, 2026 before the keynote."
    parsed, quote = parse_date_from_text(text)
    assert parsed == date(2026, 3, 12)
    assert "recorded" in quote.lower()


@pytest.mark.parametrize(
    "line",
    [
        "Welcome to our webinar on high seas governance and marine policy.",
        "Thanks for joining. Welcome to our webinar on climate adaptation.",
        "This webinar is on biodiversity in the deep ocean.",
    ],
)
def test_moderator_webinar_intro_title_is_event_keyword_only(line: str) -> None:
    assert extract_title_from_text(line) == "webinar"
    cues = extract_transcript_cues([{"text": line}])
    title_cues = [c for c in cues if c.basis == "transcript_title"]
    assert title_cues and title_cues[0].title == "webinar"
    opt = render_stem_from_cue(
        title_cues[0],
        pattern="{yymmdd}_{period}_{n}",
        transcript_stem="zoom_download",
        existing_stems=[],
    )
    assert opt is not None
    assert opt.stem == "webinar"


def test_transcript_date_beats_file_mtime_in_ranking_order() -> None:
    segments = [{"text": "Recorded on 2026-03-12. Welcome to the webinar."}]
    cues = extract_transcript_cues(segments)
    assert any(c.basis == "transcript_date" and c.confidence == "strong" for c in cues)


def test_title_only_stem_when_no_event_date() -> None:
    cue = RawRenameCue(
        basis="transcript_title",
        confidence="likely",
        detail="Title cue",
        title="Acme Product Webinar",
    )
    opt = render_stem_from_cue(
        cue,
        pattern="{yymmdd}_{period}_{n}",
        transcript_stem="zoom_download",
        existing_stems=[],
    )
    assert opt is not None
    assert opt.stem == "acme_product_webinar"


def test_file_mtime_detail_label() -> None:
    cue = RawRenameCue(
        basis="file_mtime",
        confidence="file",
        detail="File date, not the event date",
        event_date=date(2026, 1, 2),
    )
    opt = render_stem_from_cue(
        cue,
        pattern="{yymmdd}_{period}_{n}",
        transcript_stem="x",
        existing_stems=[],
    )
    assert opt is not None
    assert opt.detail == "File date, not the event date"


def test_title_token_in_pattern() -> None:
    ok, _ = validate_smart_rename_pattern("{yymmdd}_{title}")
    assert ok
    cue = RawRenameCue(
        basis="transcript_title",
        confidence="likely",
        detail="t",
        event_date=date(2026, 3, 10),
        title="Launch Call",
    )
    opt = render_stem_from_cue(
        cue,
        pattern="{yymmdd}_{title}",
        transcript_stem="old",
        existing_stems=[],
    )
    assert opt is not None
    assert opt.stem == "260310_launch_call"


def test_slug_collapses_underscores() -> None:
    assert slug_title("Acme   Product!!") == "acme_product"


def test_public_event_filename() -> None:
    assert looks_like_public_event("Zoom_Webinar_Audio.mp3", [])
    assert not looks_like_public_event("voice_memo.m4a", [])
