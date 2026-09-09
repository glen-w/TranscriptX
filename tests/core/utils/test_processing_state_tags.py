"""Tests for processing_state library tag helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.utils.processing_state import (
    get_tags_for_path,
    list_entries_by_tags,
    load_processing_state,
    mark_file_processed,
    set_tags_for_path,
)


@pytest.fixture
def state_file(tmp_path: Path) -> Path:
    return tmp_path / "processing_state.json"


@pytest.fixture
def patch_state(state_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE",
        state_file,
    )
    return state_file


def test_get_set_tags_roundtrip(tmp_path: Path, patch_state: Path) -> None:
    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}", encoding="utf-8")

    assert get_tags_for_path(transcript) == []
    saved = set_tags_for_path(transcript, ["Meeting", "idea", "Meeting", "!!"])
    assert saved == ["meeting", "idea"]
    assert get_tags_for_path(transcript) == ["meeting", "idea"]

    state = load_processing_state(state_file=patch_state, validate=False)
    _, entry = next(iter((state.get("processed_files") or {}).items()))
    assert entry["tags"] == ["meeting", "idea"]
    assert entry["tag_details"]["meeting"]["source"] == "manual"
    assert entry["tag_details"]["idea"]["source"] == "manual"


def test_set_tags_preserves_auto_source(tmp_path: Path, patch_state: Path) -> None:
    transcript = tmp_path / "auto.json"
    transcript.write_text("{}", encoding="utf-8")
    set_tags_for_path(transcript, ["meeting", "custom"], auto_tags=["meeting"])
    details = json.loads(patch_state.read_text(encoding="utf-8"))
    entry = next(iter(details["processed_files"].values()))
    assert entry["tag_details"]["meeting"]["source"] == "auto"
    assert entry["tag_details"]["custom"]["source"] == "manual"


def test_set_tags_creates_minimal_entry_when_missing(
    tmp_path: Path, patch_state: Path
) -> None:
    transcript = tmp_path / "new.json"
    transcript.write_text("{}", encoding="utf-8")
    assert not patch_state.exists()
    set_tags_for_path(transcript, ["todo"])
    assert patch_state.exists()
    assert get_tags_for_path(transcript) == ["todo"]


def test_set_tags_updates_existing_entry(tmp_path: Path, patch_state: Path) -> None:
    transcript = tmp_path / "existing.json"
    transcript.write_text("{}", encoding="utf-8")
    mark_file_processed(
        transcript,
        {"tags": ["old"], "tag_details": {"old": {"source": "manual", "confidence": 1.0}}},
    )
    set_tags_for_path(transcript, ["new"])
    assert get_tags_for_path(transcript) == ["new"]


def test_list_entries_by_tags_all_and_any(tmp_path: Path, patch_state: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    c = tmp_path / "c.json"
    for path in (a, b, c):
        path.write_text("{}", encoding="utf-8")
    set_tags_for_path(a, ["meeting", "todo"])
    set_tags_for_path(b, ["meeting"])
    set_tags_for_path(c, ["idea"])

    all_match = list_entries_by_tags(["meeting", "todo"], match="all")
    assert len(all_match) == 1
    any_match = list_entries_by_tags(["meeting", "idea"], match="any")
    assert len(any_match) == 3
    paths = {
        (entry.get("transcript_path") or entry.get("current_transcript_path"))
        for _, entry in any_match
    }
    assert {str(a.resolve()), str(b.resolve()), str(c.resolve())} == paths


def test_get_tags_uses_provided_state(tmp_path: Path) -> None:
    transcript = tmp_path / "inline.json"
    state = {
        "processed_files": {
            "uuid-1": {
                "transcript_path": str(transcript.resolve()),
                "tags": ["Reflection"],
            }
        }
    }
    with patch(
        "transcriptx.core.utils.processing_state.load_processing_state"
    ) as load_mock:
        tags = get_tags_for_path(transcript, state=state)
        load_mock.assert_not_called()
    assert tags == ["reflection"]
