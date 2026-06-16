"""Extra coverage for transcriptx.utils.text_utils."""

from __future__ import annotations

import pytest

from transcriptx.utils import text_utils as tu


@pytest.mark.unit
def test_is_turn_taking_speaker_label_allows_diarization_ids() -> None:
    assert tu.is_turn_taking_speaker_label("SPEAKER_00") is True
    assert tu.is_turn_taking_speaker_label("Speaker 2") is True


@pytest.mark.unit
def test_is_turn_taking_speaker_label_rejects_unknown_placeholders() -> None:
    assert tu.is_turn_taking_speaker_label("") is False
    assert tu.is_turn_taking_speaker_label("unknown") is False
    assert tu.is_turn_taking_speaker_label("unidentified speaker") is False


@pytest.mark.unit
def test_is_eligible_named_speaker_respects_ignored_ids() -> None:
    assert tu.is_eligible_named_speaker("Alice", "s1", {"s1"}) is False
    assert tu.is_eligible_named_speaker("Alice", "s1", None) is True


@pytest.mark.unit
def test_format_time_negative_seconds() -> None:
    assert tu.format_time(-65.0) == "-1:05"


@pytest.mark.unit
def test_format_time_detailed_negative_returns_zero() -> None:
    assert tu.format_time_detailed(-10.0) == "0:00:00"


@pytest.mark.unit
def test_clean_text_strips_artifacts() -> None:
    s = tu.clean_text("  hello  [noise] (aside)  ")
    assert "[noise]" not in s
    assert "(aside)" not in s
    assert "hello" in s


@pytest.mark.unit
def test_extractors_and_word_count_handle_empty_and_content() -> None:
    assert tu.extract_sentences("") == []
    assert tu.extract_sentences("First. Second! Third?") == ["First", "Second", "Third"]
    assert tu.count_words(" one   two\nthree ") == 3
    assert tu.extract_hashtags("Use #TranscriptX and #tests") == [
        "TranscriptX",
        "tests",
    ]
    assert tu.extract_mentions("Ping @alice and @bob") == ["alice", "bob"]


@pytest.mark.unit
def test_filename_helpers_validate_and_sanitize() -> None:
    assert tu.is_valid_filename("meeting_notes.json") is True
    assert tu.is_valid_filename("bad/name.json") is False
    assert tu.sanitize_filename(" bad/name?.json ") == "bad_name_.json"
    assert tu.sanitize_filename("") == ""


@pytest.mark.unit
def test_normalize_speaker_name_and_text() -> None:
    assert tu.normalize_speaker_name("") == "Unknown"
    assert tu.normalize_speaker_name("dr.  ada   lovelace") == "Ada Lovelace"
    assert tu.normalize_text("Cafe, TEST. 1.5") == "cafe test 1 5"
