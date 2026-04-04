"""
High-leverage unit tests for transcript simplification, language path helpers,
chart PDF utilities, and speaker display helpers.

Fast, deterministic, no external services.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.analysis.summary import charts_pdf
from transcriptx.core.utils.simplify_transcript import TranscriptSimplifier
from transcriptx.core.utils import speaker as speaker_module
from transcriptx.core.utils import transcript_languages as tl_module


@pytest.mark.unit
def test_transcript_simplifier_clean_utterance_strips_tics() -> None:
    s = TranscriptSimplifier(tics_list=["um", "uh"], agreements_list=[])
    assert s.clean_utterance("Um, hello there uh world") == "hello there world"


@pytest.mark.unit
def test_transcript_simplifier_is_agreement_true_for_phrase_words() -> None:
    s = TranscriptSimplifier(
        tics_list=[],
        agreements_list=["yeah", "right", "I agree"],
    )
    assert s.is_agreement("Yeah, right!")
    assert not s.is_agreement("We should ship Tuesday")


@pytest.mark.unit
def test_transcript_simplifier_simplify_skips_agreements_and_repetition() -> None:
    s = TranscriptSimplifier(
        tics_list=["like"],
        agreements_list=["sure"],
    )
    turns = [
        {"speaker": "A", "text": "Like, the plan is clear."},
        {"speaker": "B", "text": "Sure."},
        {"speaker": "A", "text": "The plan is clear."},
    ]
    out = s.simplify(turns)
    assert len(out) == 1
    assert out[0]["speaker"] == "A"
    assert out[0]["text"] == "the plan is clear."


@pytest.mark.unit
def test_transcript_simplifier_simplify_skips_empty_after_cleaning() -> None:
    s = TranscriptSimplifier(tics_list=["um", "uh"], agreements_list=[])
    out = s.simplify([{"speaker": "X", "text": "Um. Uh."}])
    assert out == []


@pytest.mark.unit
def test_normalize_and_validate_language_code() -> None:
    assert tl_module.normalize_language_code(None) is None
    assert tl_module.normalize_language_code("  AUTO  ") is None
    assert tl_module.normalize_language_code("FR") == "fr"
    assert tl_module.is_valid_language_code("auto")
    assert tl_module.is_valid_language_code("de")
    assert not tl_module.is_valid_language_code("")
    assert not tl_module.is_valid_language_code("eng")


@pytest.mark.unit
def test_get_transcript_path_for_language_en_vs_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path("/tmp/tx-transcripts")
    monkeypatch.setattr(tl_module, "DIARISED_TRANSCRIPTS_DIR", root)
    assert (
        tl_module.get_transcript_path_for_language("talk", None) == root / "talk.json"
    )
    assert (
        tl_module.get_transcript_path_for_language("talk", "en") == root / "talk.json"
    )
    assert (
        tl_module.get_transcript_path_for_language("talk", "es")
        == root / "es" / "talk_es.json"
    )


@pytest.mark.unit
def test_charts_pdf_natural_sort_key_orders_numeric_suffixes() -> None:
    p2 = Path("chart_2.png")
    p10 = Path("chart_10.png")
    assert charts_pdf._natural_sort_key(p2) < charts_pdf._natural_sort_key(p10)


@pytest.mark.unit
def test_charts_pdf_pixels_to_points_uses_default_dpi() -> None:
    w, h = charts_pdf._pixels_to_points(96, 96, None)
    assert w == pytest.approx(72.0)
    assert h == pytest.approx(72.0)


@pytest.mark.unit
def test_speaker_parse_and_format_display_name() -> None:
    assert speaker_module.parse_speaker_name("Glen Wright") == ("Glen", "Wright")
    assert speaker_module.parse_speaker_name("Solo") == ("Solo", None)
    assert speaker_module.format_speaker_display_name(display_name="Nick") == "Nick"
    assert (
        speaker_module.format_speaker_display_name(first_name="A", surname="B") == "A B"
    )
    assert speaker_module.format_speaker_display_name() == "Unknown"


@pytest.mark.unit
def test_get_display_speaker_name_delegates_to_is_named_speaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        speaker_module,
        "is_named_speaker",
        lambda name: name == "Real Human",
    )
    assert speaker_module.get_display_speaker_name("Real Human") == "Real Human"
    assert speaker_module.get_display_speaker_name("SPEAKER_01") is None
