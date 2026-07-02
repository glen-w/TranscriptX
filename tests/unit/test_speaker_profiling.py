"""Unit tests for speaker profile persistence helpers."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.utils import speaker_profiling as sp


@pytest.mark.unit
def test_get_speaker_profile_creates_new_profile(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sp, "SPEAKER_DIR", tmp_path)
    profile = sp.get_speaker_profile("Alice")
    assert profile["name"] == "Alice"
    assert profile["history"] == []
    path = tmp_path / "Alice.json"
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["name"] == "Alice"


@pytest.mark.unit
def test_get_speaker_profile_loads_existing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sp, "SPEAKER_DIR", tmp_path)
    existing = {
        "name": "Bob",
        "color": "#fff",
        "history": ["s1"],
        "fingerprint": {"tics": []},
    }
    (tmp_path / "Bob.json").write_text(json.dumps(existing), encoding="utf-8")
    loaded = sp.get_speaker_profile("Bob")
    assert loaded == existing


@pytest.mark.unit
def test_update_speaker_profile_persists_changes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sp, "SPEAKER_DIR", tmp_path)
    payload = {"name": "Carol", "color": "#123", "history": [], "fingerprint": {}}
    sp.update_speaker_profile("Carol", payload)
    assert json.loads((tmp_path / "Carol.json").read_text(encoding="utf-8")) == payload


@pytest.mark.unit
def test_speaker_registry_lists_and_caches_profiles(tmp_path) -> None:
    registry = sp.SpeakerRegistry(speaker_dir=tmp_path)
    (tmp_path / "Dana.json").write_text('{"name":"Dana"}', encoding="utf-8")
    assert registry.list_speakers() == ["Dana"]
    first = registry.load_profile("Dana")
    second = registry.load_profile("Dana")
    assert first is second
    assert first["name"] == "Dana"
