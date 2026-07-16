"""Lock path canonicalisation alias tests."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.run_writer_locks import run_lock_path_for_canonical_root


def test_relative_absolute_redundant_same_lock(tmp_path, monkeypatch):
    state = tmp_path / "state"
    target = tmp_path / "outputs" / "slug" / "run1"
    target.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    a = run_lock_path_for_canonical_root(target, state_dir=state)
    b = run_lock_path_for_canonical_root(Path("outputs/slug/run1"), state_dir=state)
    c = run_lock_path_for_canonical_root(
        tmp_path / "outputs" / "slug" / "." / "run1", state_dir=state
    )
    assert a == b == c


def test_different_roots_different_locks(tmp_path):
    state = tmp_path / "state"
    a = run_lock_path_for_canonical_root(tmp_path / "a" / "r", state_dir=state)
    b = run_lock_path_for_canonical_root(tmp_path / "b" / "r", state_dir=state)
    assert a != b
