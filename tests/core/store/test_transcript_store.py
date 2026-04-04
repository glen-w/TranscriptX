"""Unit tests for TranscriptStore (sole writer for transcript JSON)."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.store import TranscriptStore


def test_transcript_store_read_write(tmp_path) -> None:
    path = tmp_path / "t.json"
    data = {"segments": [{"speaker": "A", "text": "Hi"}], "metadata": {}}
    store = TranscriptStore()
    store.write(path, data, reason="test")
    assert path.exists()
    read_back = store.read(path)
    assert read_back["segments"] == data["segments"]
    assert "_last_modified_by" in read_back
    assert read_back["_last_modified_by"] == "test"
    assert "_last_modified_at" in read_back


def test_transcript_store_mutate(tmp_path) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"segments": [], "x": 1}))
    store = TranscriptStore()

    def add_segment(d: dict) -> None:
        d["segments"].append({"speaker": "S1", "text": "Hello"})

    result = store.mutate(path, add_segment, reason="mutate_test")
    assert len(result["segments"]) == 1
    assert result["segments"][0]["speaker"] == "S1"
    assert result["_last_modified_by"] == "mutate_test"

    # Read again from disk
    again = store.read(path)
    assert again["segments"][0]["text"] == "Hello"


def test_transcript_store_read_missing_raises(tmp_path) -> None:
    store = TranscriptStore()
    with pytest.raises(FileNotFoundError):
        store.read(tmp_path / "nonexistent.json")


def test_transcript_store_write_creates_parent_dirs(tmp_path) -> None:
    path = tmp_path / "sub" / "dir" / "t.json"
    store = TranscriptStore()
    store.write(path, {"segments": []}, reason="test")
    assert path.exists()
