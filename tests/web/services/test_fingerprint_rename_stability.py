"""Characterisation: content fingerprint stable across same-FS rename."""

from __future__ import annotations

import os
from pathlib import Path

from transcriptx.web.services.run_cleanup.fingerprint import compute_tree_fingerprint


def test_content_fingerprint_stable_across_rename(tmp_path: Path):
    run = tmp_path / "run_a"
    run.mkdir()
    (run / "a.txt").write_text("hello", encoding="utf-8")
    (run / "sub").mkdir()
    (run / "sub" / "b.txt").write_text("world", encoding="utf-8")
    st = run.lstat()
    fp1, size1, count1 = compute_tree_fingerprint(run, int(st.st_dev))
    dest = tmp_path / "run_b"
    os.rename(run, dest)
    st2 = dest.lstat()
    assert int(st2.st_dev) == int(st.st_dev)
    assert int(st2.st_ino) == int(st.st_ino)
    fp2, size2, count2 = compute_tree_fingerprint(dest, int(st.st_dev))
    assert fp1 == fp2
    assert size1 == size2
    assert count1 == count2


def test_fingerprint_rejects_wrong_planned_device(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "a.txt").write_text("x", encoding="utf-8")
    st = run.lstat()
    from transcriptx.web.services.run_cleanup.fingerprint import TreeFingerprintError
    import pytest

    with pytest.raises(TreeFingerprintError):
        compute_tree_fingerprint(run, int(st.st_dev) + 999999)
