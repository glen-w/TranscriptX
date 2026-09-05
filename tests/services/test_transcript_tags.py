"""Tests for TranscriptTagService persistence and merge rules."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.processing_state import find_processed_entry_for_path
from transcriptx.services.transcript_tags import TranscriptTagService


def _segments() -> list[dict]:
    return [
        {
            "speaker": "Alice",
            "text": "I have an idea for the meeting agenda.",
            "start": 0.0,
            "end": 2.0,
        }
    ]


def test_save_and_get_tags(tmp_path, monkeypatch) -> None:
    state_file = tmp_path / "processing_state.json"
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
        state_file,
    )
    transcript = tmp_path / "talk.json"
    transcript.write_text("{}", encoding="utf-8")
    service = TranscriptTagService()
    service.save_tags(transcript, ["Meeting", "meeting", "custom"])
    assert service.get_tags(transcript) == ["meeting", "custom"]
    _, entry = find_processed_entry_for_path(str(transcript))
    assert entry is not None
    assert entry["tags"] == ["meeting", "custom"]


def test_initialize_from_extraction_does_not_overwrite(tmp_path, monkeypatch) -> None:
    state_file = tmp_path / "processing_state.json"
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
        state_file,
    )
    transcript = tmp_path / "talk.json"
    transcript.write_text("{}", encoding="utf-8")
    service = TranscriptTagService()
    service.save_tags(transcript, ["manual"])
    result = service.initialize_from_extraction(
        transcript, {"tags": ["meeting"], "tag_details": {}}
    )
    assert result["initialized"] is False
    assert service.get_tags(transcript) == ["manual"]


def test_extract_and_persist_batch_initializes_once(tmp_path, monkeypatch) -> None:
    state_file = tmp_path / "processing_state.json"
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
        state_file,
    )
    transcript = tmp_path / "talk.json"
    transcript.write_text("{}", encoding="utf-8")
    service = TranscriptTagService()
    first = service.extract_and_persist(transcript, _segments(), batch_mode=True)
    assert first.get("initialized") is True
    assert "idea" in first["tags"] or "meeting" in first["tags"]
    service.save_tags(transcript, [])
    second = service.extract_and_persist(transcript, _segments(), batch_mode=True)
    assert second.get("initialized") is False
    assert second["tags"] == []


def test_suggest_auto_tags_merges(tmp_path, monkeypatch) -> None:
    state_file = tmp_path / "processing_state.json"
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
        state_file,
    )
    transcript = tmp_path / "talk.json"
    transcript.write_text("{}", encoding="utf-8")
    service = TranscriptTagService()
    service.save_tags(transcript, ["custom"])
    result = service.suggest_auto_tags(transcript, _segments())
    assert "custom" in result["tags"]
    assert "idea" in result["tags"] or "meeting" in result["tags"]
