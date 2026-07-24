"""Unit tests for Speakers-detail run artifact join helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.speaker_profiles.run_artifact_join import (
    newest_run_with,
    pick_speaker_entry,
)


@pytest.mark.unit
def test_pick_speaker_entry_casefold_and_empty() -> None:
    assert pick_speaker_entry(None, frozenset({"alice"})) is None
    assert pick_speaker_entry({}, frozenset({"alice"})) is None
    assert pick_speaker_entry({"Bob": 1}, frozenset({"alice"})) is None
    key, value = pick_speaker_entry({"Alice": 0.5, "Bob": 0.1}, frozenset({"alice"}))
    assert key == "Alice"
    assert value == 0.5
    key2, _ = pick_speaker_entry({"ALLY": 9}, frozenset({"ally"}))
    assert key2 == "ALLY"


@pytest.mark.unit
def test_newest_run_with_mtime_and_name_tiebreak(tmp_path: Path) -> None:
    session = tmp_path / "sess"
    older = session / "run_a"
    newer = session / "run_b"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / "hit.json").write_text("{}", encoding="utf-8")
    (newer / "hit.json").write_text("{}", encoding="utf-8")

    import os
    import time

    t0 = time.time() - 50
    t1 = time.time()
    os.utime(older, (t0, t0))
    os.utime(newer, (t1, t1))

    def find(run_root: Path) -> Path | None:
        p = run_root / "hit.json"
        return p if p.is_file() else None

    found = newest_run_with("sess", find, outputs_dir=tmp_path)
    assert found is not None
    run_id, path = found
    assert run_id == "run_b"
    assert path.name == "hit.json"

    # Hidden / missing artifact dirs ignored
    (session / ".cache").mkdir()
    (session / "run_empty").mkdir()
    found2 = newest_run_with("sess", find, outputs_dir=tmp_path)
    assert found2 is not None
    assert found2[0] == "run_b"

    assert newest_run_with("missing", find, outputs_dir=tmp_path) is None
