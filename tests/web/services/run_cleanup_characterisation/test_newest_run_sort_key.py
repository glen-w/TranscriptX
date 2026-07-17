"""Characterise newest_run_sort_key_desc as used by cleanup partition.

Do not change production sort behaviour during Phase A. The ascending key
paired with reverse=True is the frozen baseline (even though the ascending
and _desc helpers currently return identical tuples).
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.run_identity import (
    newest_run_sort_key,
    newest_run_sort_key_desc,
)
from transcriptx.web.services.run_cleanup import CleanupMode
from transcriptx.web.services.run_cleanup.plan_builder import partition_for_mode

from . import assert_golden, make_service, mk_run


def test_desc_key_identical_to_ascending_helper():
    """Document current implementation: both helpers return the same tuple."""
    args = {"mtime_ns": 42, "run_id": "r1", "path": "/p"}
    assert newest_run_sort_key(**args) == newest_run_sort_key_desc(**args)
    assert_golden(
        "newest_run_sort_key_identity.json",
        {
            "ascending_equals_desc": True,
            "sample_key": list(newest_run_sort_key_desc(**args)),
            "usage": "sorted(..., key=newest_run_sort_key_desc, reverse=True)",
        },
    )


def test_desc_with_reverse_true_orders_higher_mtime_first():
    rows = [
        {"mtime_ns": 1, "run_id": "a", "path": "/a"},
        {"mtime_ns": 3, "run_id": "b", "path": "/b"},
        {"mtime_ns": 2, "run_id": "c", "path": "/c"},
    ]
    ordered = sorted(
        rows,
        key=lambda r: newest_run_sort_key_desc(
            mtime_ns=r["mtime_ns"], run_id=r["run_id"], path=r["path"]
        ),
        reverse=True,
    )
    assert [r["run_id"] for r in ordered] == ["b", "c", "a"]


def test_equal_mtime_lexical_run_id_tiebreak():
    rows = [
        {"mtime_ns": 10, "run_id": "run_a", "path": "/a"},
        {"mtime_ns": 10, "run_id": "run_c", "path": "/c"},
        {"mtime_ns": 10, "run_id": "run_b", "path": "/b"},
    ]
    ordered = sorted(
        rows,
        key=lambda r: newest_run_sort_key_desc(
            mtime_ns=r["mtime_ns"], run_id=r["run_id"], path=r["path"]
        ),
        reverse=True,
    )
    # reverse=True on (mtime, run_id, path) → higher run_id string first.
    assert [r["run_id"] for r in ordered] == ["run_c", "run_b", "run_a"]
    assert_golden(
        "newest_run_equal_mtime_tiebreak.json",
        {"ordered_run_ids": [r["run_id"] for r in ordered]},
    )


def test_partition_delete_old_uses_desc_reverse_true(tmp_path: Path):
    """DELETE_OLD retains the first element after desc+reverse=True sort."""
    from dataclasses import replace

    svc = make_service(tmp_path)
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001", content="1")
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000002", content="2")
    plan = svc._build_plan(CleanupMode.DELETE_ALL)
    eligible = list(plan.candidates)
    # Force equal mtimes so run_id lexical order decides newest under reverse=True.
    equal = [replace(t, mtime_ns=1000) for t in eligible]
    candidates, retained = partition_for_mode(CleanupMode.DELETE_OLD, equal)
    assert len(retained) == 1
    assert len(candidates) == 1
    # Higher run_id string wins when mtimes equal and reverse=True.
    assert retained[0].run_id == "20200101_000000_00000002"
    assert_golden(
        "partition_equal_mtime_retained.json",
        {
            "retained_run_id": retained[0].run_id,
            "candidate_run_ids": [c.run_id for c in candidates],
        },
    )
