"""Domain unit tests for Group ↔ TranscriptSet bridging."""

from __future__ import annotations

import pytest

from transcriptx.core.domain.group import Group
from transcriptx.core.domain.transcript_set import TranscriptSet


@pytest.mark.unit
def test_group_to_transcript_set_injects_metadata() -> None:
    group = Group(
        group_id="g-1",
        name="Workshop",
        members=["transcripts/a.json", "transcripts/b.json"],
        metadata={"source": "test"},
    )
    ts = group.to_transcript_set(["/abs/a.json", "/abs/b.json"])
    assert ts.key == "g-1"
    assert ts.name == "Workshop"
    assert ts.transcript_ids == ["/abs/a.json", "/abs/b.json"]
    assert ts.metadata["group_uuid"] == "g-1"
    assert ts.metadata["group_key"] == "g-1"
    assert ts.metadata["source"] == "test"


@pytest.mark.unit
def test_transcript_set_roundtrip_and_resolve() -> None:
    original = TranscriptSet.create(
        ["/a.json", "/b.json"],
        name="G",
        metadata={"group_uuid": "g", "transcript_id_map": {"/a.json": 1}},
    )
    restored = TranscriptSet.from_dict(original.to_dict())
    assert restored == original
    assert restored.resolve_transcripts() == ["/a.json", "/b.json"]
    assert restored.resolve_transcripts(lambda p: f"resolved:{p}") == [
        "resolved:/a.json",
        "resolved:/b.json",
    ]


@pytest.mark.unit
def test_transcript_set_compute_key_is_order_sensitive() -> None:
    assert TranscriptSet.compute_key(["a", "b"]) != TranscriptSet.compute_key(
        ["b", "a"]
    )
    assert Group.compute_key(["A", "B"]) == Group.compute_key(["a", "b"])
    assert Group.compute_key(["a", "b"]) != Group.compute_key(["b", "a"])
