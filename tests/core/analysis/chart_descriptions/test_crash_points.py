"""Crash / idempotency tests for chart_descriptions publisher."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.analysis.chart_descriptions.generate import run_chart_descriptions
from transcriptx.core.analysis.chart_descriptions.inventory import LogicalChartInventory
from transcriptx.core.analysis.chart_descriptions.paths import (
    generation_dir,
    generations_dir,
)
from transcriptx.core.analysis.chart_descriptions.publisher import (
    active_matches_attempt,
    gc_uncommitted_generations,
    new_attempt_epoch,
    new_generation_id,
    read_active,
    write_attempt_epoch,
)


class _FakeClient:
    def __init__(self) -> None:
        self.calls = 0
        self.model = "fake"

    def generate(self, *args, **kwargs):
        self.calls += 1
        return json.dumps({"description": "ok"})


def _empty_run(tmp_path: Path) -> Path:
    run_root = tmp_path / "run"
    run_root.mkdir()
    return run_root


def test_duplicate_skipped_finalizer_invocations(tmp_path: Path):
    run_root = _empty_run(tmp_path)
    inventory = LogicalChartInventory(
        run_root=str(run_root), run_kind="transcript", run_target_id="t"
    )
    snap = inventory.snapshot_sha256()
    cfg = type("C", (), {"analysis": None, "llm": None})()
    client = _FakeClient()
    r1 = run_chart_descriptions(
        run_root=run_root,
        run_id="r",
        inventory=inventory,
        inventory_snapshot_sha256=snap,
        chart_set="all",
        selected=False,
        enabled=True,
        llm_enabled=True,
        config=cfg,
        client_factory=lambda: client,
    )
    r2 = run_chart_descriptions(
        run_root=run_root,
        run_id="r",
        inventory=inventory,
        inventory_snapshot_sha256=snap,
        chart_set="all",
        selected=False,
        enabled=True,
        llm_enabled=True,
        config=cfg,
        client_factory=lambda: client,
    )
    assert r1.published and r2.published
    assert client.calls == 0
    assert active_matches_attempt(run_root)
    active = read_active(run_root)
    assert active and active.get("generation_id") == r2.generation_id


def test_orphaned_staging_cleanup(tmp_path: Path):
    run_root = _empty_run(tmp_path)
    orphan_id = new_generation_id()
    orphan = generation_dir(run_root, orphan_id)
    orphan.mkdir(parents=True)
    (orphan / "partial.json").write_text("{}", encoding="utf-8")
    # No COMMIT.json
    removed = gc_uncommitted_generations(run_root, keep_generation_id=None)
    assert orphan_id in removed
    assert not orphan.exists()


def test_attempt_epoch_tombstone_before_commit_suppresses_prior(tmp_path: Path):
    run_root = _empty_run(tmp_path)
    inventory = LogicalChartInventory(
        run_root=str(run_root), run_kind="transcript", run_target_id="t"
    )
    snap = inventory.snapshot_sha256()
    cfg = type("C", (), {"analysis": None, "llm": None})()
    r1 = run_chart_descriptions(
        run_root=run_root,
        run_id="r",
        inventory=inventory,
        inventory_snapshot_sha256=snap,
        chart_set="all",
        selected=True,
        enabled=False,
        llm_enabled=True,
        config=cfg,
        client_factory=lambda: _FakeClient(),
    )
    assert r1.published
    # Simulate crash: new attempt epoch without completing ACTIVE flip
    write_attempt_epoch(
        run_root,
        attempt_epoch=new_attempt_epoch(),
        generation_id=new_generation_id(),
    )
    assert not active_matches_attempt(run_root)
