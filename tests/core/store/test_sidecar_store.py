from __future__ import annotations

import json

from transcriptx.core.store import SidecarStore


def test_read_returns_none_when_missing(tmp_path) -> None:
    store = SidecarStore()
    path = tmp_path / "sample.speaker_map.json"

    assert store.read(path) is None


def test_write_creates_file_atomically(tmp_path) -> None:
    store = SidecarStore()
    path = tmp_path / "sample.speaker_map.json"
    payload = {"speaker_map": {"SPEAKER_00": "Alice"}}

    store.write(path, payload, reason="test")

    assert path.exists()
    assert json.loads(path.read_text()) == payload
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_mutate_creates_file_on_first_write(tmp_path) -> None:
    store = SidecarStore()
    path = tmp_path / "sample.speaker_map.json"

    result = store.mutate(
        path,
        lambda data: data.update(
            {
                "speaker_map": {"SPEAKER_00": "Alice"},
                "ignored_speakers": ["SPEAKER_01"],
            }
        ),
        reason="test",
    )

    assert result == {
        "speaker_map": {"SPEAKER_00": "Alice"},
        "ignored_speakers": ["SPEAKER_01"],
    }
    assert json.loads(path.read_text()) == result


def test_mutate_updates_existing_sidecar(tmp_path) -> None:
    store = SidecarStore()
    path = tmp_path / "sample.speaker_map.json"
    path.write_text(json.dumps({"speaker_map": {"SPEAKER_00": "Alice"}}))

    result = store.mutate(
        path,
        lambda data: data.setdefault("ignored_speakers", []).append("SPEAKER_01"),
        reason="test",
    )

    assert result["speaker_map"] == {"SPEAKER_00": "Alice"}
    assert result["ignored_speakers"] == ["SPEAKER_01"]
    assert json.loads(path.read_text()) == result
