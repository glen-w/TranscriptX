from transcriptx.core.utils.canonicalization import (
    compute_transcript_content_hash,
    normalize_text,
)


def test_normalize_text_strips_and_normalizes_newlines() -> None:
    text = "  Hello\r\nWorld  \n"
    assert normalize_text(text) == "Hello\nWorld"


def test_transcript_hash_stable_for_whitespace_changes() -> None:
    segments_a = [
        {"start": 0.0, "end": 1.2345, "speaker": "SPEAKER_00", "text": " Hello world "},
    ]
    segments_b = [
        {"start": 0.0, "end": 1.2345, "speaker": "SPEAKER_00", "text": "Hello world"},
    ]
    assert compute_transcript_content_hash(segments_a) == compute_transcript_content_hash(segments_b)


def test_transcript_hash_changes_on_text_change() -> None:
    segments_a = [
        {"start": 0.0, "end": 1.2345, "speaker": "SPEAKER_00", "text": "Hello world"},
    ]
    segments_b = [
        {"start": 0.0, "end": 1.2345, "speaker": "SPEAKER_00", "text": "Hello there"},
    ]
    assert compute_transcript_content_hash(segments_a) != compute_transcript_content_hash(segments_b)
