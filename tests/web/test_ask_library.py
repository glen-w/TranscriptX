"""Ask page question library helpers."""

from __future__ import annotations

from transcriptx.web.components.ask_question_library import (
    filter_global_scope_library_questions,
    library_question_label,
)


def test_filter_global_scope_library_questions() -> None:
    rows = [
        {"text": "  What was decided?  ", "scopes": {"global": True, "per_speaker": False}},
        {"text": "Per person only", "scopes": {"global": False, "per_speaker": True}},
        {"text": "", "scopes": {"global": True, "per_speaker": False}},
    ]
    out = filter_global_scope_library_questions(rows)
    assert len(out) == 1
    assert out[0]["text"] == "What was decided?"


def test_library_question_label_shows_scope_badges() -> None:
    label = library_question_label(
        {"text": "Hello", "scopes": {"global": True, "per_speaker": True}}
    )
    assert label == "Hello [GS]"
