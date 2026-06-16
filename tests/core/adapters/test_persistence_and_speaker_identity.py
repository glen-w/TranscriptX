"""Small adapter implementations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.adapters.persistence_adapter import (
    NullPersistenceAdapter,
)
from transcriptx.core.adapters.speaker_identity_store import (
    FileBasedSpeakerIdentityStore,
)


@pytest.mark.unit
def test_null_persistence_adapter_noops() -> None:
    a = NullPersistenceAdapter()
    a.persist_transcript("/t.json", {"k": 1})
    a.persist_run({"id": 1})
    a.persist_artifacts({})


@pytest.mark.unit
def test_file_based_speaker_identity_store_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "ident.json"
    store = FileBasedSpeakerIdentityStore(p)
    assert store.load("k1") is None
    store.save("k1", {"names": ["a"]})
    assert store.load("k1") == {"names": ["a"]}
    store.save("k2", {"x": 1})
    data = json.loads(p.read_text(encoding="utf-8"))
    assert set(data.keys()) == {"k1", "k2"}
