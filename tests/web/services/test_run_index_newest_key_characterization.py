"""Characterization / contract tests for RunIndex newest-run tie-breaker.

Documents that RunIndex orders by ``run_summary_newest_key`` (mtime_ns, then
run_id, then path) rather than ``last_updated`` float alone.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.core.utils.run_identity import run_summary_newest_key
from transcriptx.web.services.run_index import RunIndex, RunSummary


def _make_viewable(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    # Minimal marker that is_viewable_run / has_user_artifacts typically accept
    (run_dir / "report.json").write_text("{}", encoding="utf-8")


@pytest.fixture
def outputs_layout(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs"
    groups = outputs / "groups"
    outputs.mkdir()
    groups.mkdir()
    monkeypatch.setattr("transcriptx.web.services.run_index.OUTPUTS_DIR", outputs)
    monkeypatch.setattr("transcriptx.web.services.run_index.GROUP_OUTPUTS_DIR", groups)
    monkeypatch.setattr(
        "transcriptx.web.services.run_index.is_viewable_run",
        lambda _p: True,
    )
    return outputs, groups


class TestRunIndexNewestKey:
    def test_sort_uses_mtime_ns_primary(self, outputs_layout):
        outputs, _groups = outputs_layout
        slug = outputs / "demo_slug"
        older = slug / "20200101_000000_00000001"
        newer = slug / "20200101_000000_00000002"
        _make_viewable(older)
        _make_viewable(newer)

        # Force identical second-resolution mtimes but distinct ns if possible;
        # set explicit mtimes via os.utime.
        import os

        os.utime(older, ns=(1_000_000_000, 1_000_000_000))
        os.utime(newer, ns=(2_000_000_000, 2_000_000_000))

        scope = SimpleNamespace(scope_type="transcript", uuid=None)
        runs = RunIndex.list_runs(scope, subject_id="demo_slug")
        assert [r.run_id for r in runs] == [
            "20200101_000000_00000002",
            "20200101_000000_00000001",
        ]
        assert runs[0].mtime_ns == 2_000_000_000
        assert runs[1].mtime_ns == 1_000_000_000

    def test_tie_break_by_run_id_when_mtime_ns_equal(self, outputs_layout):
        outputs, _groups = outputs_layout
        slug = outputs / "demo_slug"
        a = slug / "20200101_000000_aaaaaaaa"
        b = slug / "20200101_000000_bbbbbbbb"
        _make_viewable(a)
        _make_viewable(b)

        import os

        same_ns = 5_000_000_000
        os.utime(a, ns=(same_ns, same_ns))
        os.utime(b, ns=(same_ns, same_ns))

        scope = SimpleNamespace(scope_type="transcript", uuid=None)
        runs = RunIndex.list_runs(scope, subject_id="demo_slug")
        # reverse=True on (mtime_ns, run_id, path) → higher run_id first
        assert [r.run_id for r in runs] == [
            "20200101_000000_bbbbbbbb",
            "20200101_000000_aaaaaaaa",
        ]

    def test_run_summary_newest_key_matches_index_order(self):
        runs = [
            RunSummary(
                run_id="a",
                run_root=Path("/tmp/a"),
                last_updated=1.0,
                mtime_ns=1_000,
            ),
            RunSummary(
                run_id="b",
                run_root=Path("/tmp/b"),
                last_updated=1.0,
                mtime_ns=1_000,
            ),
            RunSummary(
                run_id="c",
                run_root=Path("/tmp/c"),
                last_updated=2.0,
                mtime_ns=2_000,
            ),
        ]
        ordered = sorted(runs, key=run_summary_newest_key, reverse=True)
        assert [r.run_id for r in ordered] == ["c", "b", "a"]

    def test_mtime_ns_populated_via_lstat(self, outputs_layout):
        outputs, _groups = outputs_layout
        slug = outputs / "demo_slug"
        run = slug / "20200101_120000_abcd1234"
        _make_viewable(run)
        scope = SimpleNamespace(scope_type="transcript", uuid=None)
        runs = RunIndex.list_runs(scope, subject_id="demo_slug")
        assert len(runs) == 1
        assert runs[0].mtime_ns is not None
        assert runs[0].last_updated is not None
