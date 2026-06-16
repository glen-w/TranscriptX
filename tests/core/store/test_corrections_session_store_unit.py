"""Corrections session store layout and I/O (isolated data root)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from transcriptx.core.store import corrections_session_store as cs


@pytest.fixture
def iso_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "corrections"
    monkeypatch.setattr(cs, "_CORRECTIONS_ROOT", root)
    return root


@pytest.mark.unit
def test_session_shard_and_paths() -> None:
    assert cs.session_dir_for_session_id("ab12").name == "ab12"
    assert "ab" in str(cs.session_dir_for_session_id("ab12"))
    assert cs.events_path_for_session_id("sid").name == "events.jsonl"


@pytest.mark.unit
def test_store_write_read_round_trip(iso_root: Path, tmp_path: Path) -> None:
    tjson = tmp_path / "meet.json"
    tjson.write_text("{}", encoding="utf-8")
    transcript_path = str(tjson.resolve())
    store = cs.CorrectionsSessionStore()
    payload = {
        "studio_schema_version": 1,
        "session_id": "sess_one",
        "transcript_path": transcript_path,
        "recorded_transcript_identity_hash": "fp",
        "candidates": [],
    }
    store.write(transcript_path, payload)
    loaded = store.read(transcript_path)
    assert loaded is not None
    assert loaded["session_id"] == "sess_one"


@pytest.mark.unit
def test_find_by_session_id_after_write(iso_root: Path, tmp_path: Path) -> None:
    tjson = tmp_path / "x.json"
    tjson.write_text("{}", encoding="utf-8")
    transcript_path = str(tjson.resolve())
    store = cs.CorrectionsSessionStore()
    store.write(
        transcript_path,
        {
            "studio_schema_version": 1,
            "session_id": "find_me",
            "transcript_path": transcript_path,
            "recorded_transcript_identity_hash": "",
            "candidates": [],
        },
    )
    got = store.find_by_session_id("find_me")
    assert got is not None
    assert got["session_id"] == "find_me"


@pytest.mark.unit
def test_append_event_jsonl_and_read_lines(iso_root: Path) -> None:
    store = cs.CorrectionsSessionStore()
    store.append_event_jsonl("ev1", {"a": 1})
    lines = store.read_event_lines("ev1")
    assert len(lines) == 1
    assert json.loads(lines[0].strip()) == {"a": 1}


@pytest.mark.unit
def test_ensure_session_creates_minimal_blob(iso_root: Path, tmp_path: Path) -> None:
    tjson = tmp_path / "new.json"
    tjson.write_text("{}", encoding="utf-8")
    p = str(tjson.resolve())
    store = cs.CorrectionsSessionStore()
    doc = store.ensure_session(p, session_id="fixed_id")
    assert doc["session_id"] == "fixed_id"
    again = store.read(p)
    assert again is not None
    assert again["session_id"] == "fixed_id"


@pytest.mark.unit
def test_mutate_updates_session(iso_root: Path, tmp_path: Path) -> None:
    tjson = tmp_path / "m.json"
    tjson.write_text("{}", encoding="utf-8")
    p = str(tjson.resolve())
    store = cs.CorrectionsSessionStore()
    store.ensure_session(p, session_id="mut")
    store.mutate(p, lambda d: d.update({"status": "closed"}))
    assert store.read(p).get("status") == "closed"


@pytest.mark.unit
def test_rebuild_sessions_index_from_session_roots(
    iso_root: Path, tmp_path: Path
) -> None:
    tjson = tmp_path / "idx.json"
    tjson.write_text("{}", encoding="utf-8")
    tp = str(tjson.resolve())
    store = cs.CorrectionsSessionStore()
    store.write(
        tp,
        {
            "studio_schema_version": 1,
            "session_id": "idx_sess",
            "transcript_path": tp,
            "recorded_transcript_identity_hash": "h",
            "updated_at": "2026-01-01T00:00:00Z",
            "candidates": [],
        },
    )
    idx = cs.rebuild_sessions_index_from_session_roots()
    assert "idx_sess" in idx.get("entries", {})


# --- shard derivation branches ---


@pytest.mark.unit
def test_shard_long_id_uses_first_two_lowercased() -> None:
    assert cs._shard("ABcdef") == "ab"


@pytest.mark.unit
def test_shard_single_char_is_padded() -> None:
    assert cs._shard("x") == "x0"


@pytest.mark.unit
def test_shard_empty_or_symbols_only_falls_back_to_00() -> None:
    assert cs._shard("") == "00"
    # Non-alphanumeric characters are normalized to underscores, still length>=2.
    assert cs._shard("@#") == "__"


# --- index loader resilience ---


@pytest.mark.unit
def test_load_index_missing_returns_default(iso_root: Path) -> None:
    store = cs.CorrectionsSessionStore()
    idx = store._load_index()
    assert idx == {"index_schema_version": 1, "entries": {}}


@pytest.mark.unit
def test_load_index_non_dict_json_returns_default(iso_root: Path) -> None:
    p = cs.index_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("[1, 2, 3]", encoding="utf-8")
    store = cs.CorrectionsSessionStore()
    assert store._load_index() == {"index_schema_version": 1, "entries": {}}


@pytest.mark.unit
def test_load_index_adds_missing_entries_key(iso_root: Path) -> None:
    p = cs.index_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"index_schema_version": 1}), encoding="utf-8")
    store = cs.CorrectionsSessionStore()
    idx = store._load_index()
    assert idx["entries"] == {}


@pytest.mark.unit
def test_load_index_corrupt_json_returns_default(iso_root: Path) -> None:
    p = cs.index_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    store = cs.CorrectionsSessionStore()
    assert store._load_index() == {"index_schema_version": 1, "entries": {}}


# --- read/write branches ---


@pytest.mark.unit
def test_write_without_index_falls_back_to_legacy_read(
    iso_root: Path, tmp_path: Path
) -> None:
    tjson = tmp_path / "noidx.json"
    tjson.write_text("{}", encoding="utf-8")
    tp = str(tjson.resolve())
    store = cs.CorrectionsSessionStore()
    store.write(
        tp,
        {
            "studio_schema_version": 1,
            "session_id": "no_index_sess",
            "transcript_path": tp,
            "recorded_transcript_identity_hash": "",
            "candidates": [],
        },
        update_index=False,
    )
    # Index has no entry, so read falls back to legacy stem-dir lookup.
    assert "no_index_sess" not in store._load_index().get("entries", {})
    legacy = cs.session_path_for_transcript(tp)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        json.dumps({"session_id": "legacy_blob", "transcript_path": tp}),
        encoding="utf-8",
    )
    loaded = store.read(tp)
    assert loaded is not None
    assert loaded["session_id"] == "legacy_blob"


@pytest.mark.unit
def test_read_unknown_transcript_returns_none(iso_root: Path, tmp_path: Path) -> None:
    store = cs.CorrectionsSessionStore()
    missing = tmp_path / "ghost.json"
    missing.write_text("{}", encoding="utf-8")
    assert store.read(str(missing.resolve())) is None


@pytest.mark.unit
def test_write_requires_session_id(iso_root: Path, tmp_path: Path) -> None:
    tjson = tmp_path / "x.json"
    tjson.write_text("{}", encoding="utf-8")
    store = cs.CorrectionsSessionStore()
    with pytest.raises(ValueError):
        store.write(str(tjson.resolve()), {"candidates": []})


@pytest.mark.unit
def test_mutate_without_existing_session_raises(iso_root: Path, tmp_path: Path) -> None:
    tjson = tmp_path / "absent.json"
    tjson.write_text("{}", encoding="utf-8")
    store = cs.CorrectionsSessionStore()
    with pytest.raises(ValueError):
        store.mutate(str(tjson.resolve()), lambda d: None)


# --- find_by_session_id fallbacks ---


@pytest.mark.unit
def test_find_by_session_id_unknown_returns_none(iso_root: Path) -> None:
    store = cs.CorrectionsSessionStore()
    assert store.find_by_session_id("does_not_exist") is None


@pytest.mark.unit
def test_find_by_session_id_scans_session_roots_without_index(
    iso_root: Path,
) -> None:
    # Write a session.json directly under the sharded layout, no index entry.
    sid = "scan_sess"
    sdir = cs.session_dir_for_session_id(sid)
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "session.json").write_text(
        json.dumps({"session_id": sid, "transcript_path": "/t.json"}),
        encoding="utf-8",
    )
    store = cs.CorrectionsSessionStore()
    found = store.find_by_session_id(sid)
    assert found is not None
    assert found["session_id"] == sid


# --- events ---


@pytest.mark.unit
def test_read_event_lines_missing_returns_empty(iso_root: Path) -> None:
    store = cs.CorrectionsSessionStore()
    assert store.read_event_lines("no_events") == []


@pytest.mark.unit
def test_write_and_append_event_writes_both(iso_root: Path, tmp_path: Path) -> None:
    tjson = tmp_path / "wae.json"
    tjson.write_text("{}", encoding="utf-8")
    tp = str(tjson.resolve())
    store = cs.CorrectionsSessionStore()
    store.write_and_append_event(
        tp,
        {"session_id": "wae_sess", "transcript_path": tp, "candidates": []},
        {"type": "created"},
    )
    assert store.read_event_lines("wae_sess")
    assert store.find_by_session_id("wae_sess")["session_id"] == "wae_sess"


@pytest.mark.unit
def test_ensure_session_returns_existing_without_overwrite(
    iso_root: Path, tmp_path: Path
) -> None:
    tjson = tmp_path / "ex.json"
    tjson.write_text("{}", encoding="utf-8")
    tp = str(tjson.resolve())
    store = cs.CorrectionsSessionStore()
    first = store.ensure_session(tp, session_id="keep")
    first_created = first["created_at"]
    again = store.ensure_session(tp, session_id="ignored_second_id")
    assert again["session_id"] == "keep"
    assert again["created_at"] == first_created


@pytest.mark.unit
def test_rebuild_index_empty_root_writes_default(iso_root: Path) -> None:
    idx = cs.rebuild_sessions_index_from_session_roots()
    assert idx == {"index_schema_version": 1, "entries": {}}
