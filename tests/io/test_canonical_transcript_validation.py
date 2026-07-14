"""Tests for canonical transcript validation."""

from pathlib import Path

from transcriptx.io.canonical_transcript_validation import (
    CanonicalTranscriptCategory,
    validate_canonical_transcript,
    is_canonical_transcript,
)


def test_validate_canonical_transcript_rejects_missing(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    result = validate_canonical_transcript(path)
    assert result.ok is False
    assert result.category == CanonicalTranscriptCategory.not_found


def test_validate_canonical_transcript_rejects_bad_extension(tmp_path: Path) -> None:
    path = tmp_path / "not_json.txt"
    path.write_text("{}", encoding="utf-8")
    result = validate_canonical_transcript(path)
    assert result.ok is False
    assert result.category == CanonicalTranscriptCategory.bad_extension


def test_validate_canonical_transcript_accepts_minimal_valid(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text(
        '{"schema_version": "1.0", "source": {"type": "manual", "original_path": "t.json", "imported_at": "2020-01-01T00:00:00+00:00"}, "segments": []}',
        encoding="utf-8",
    )
    result = validate_canonical_transcript(path)
    assert result.ok is True
    assert result.category == CanonicalTranscriptCategory.ok
    assert is_canonical_transcript(path) is True
