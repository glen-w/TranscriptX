"""Characterisation: fault-point registry freeze and mutation-relative order."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.services.run_cleanup import CleanupMode
from transcriptx.web.services.run_cleanup.faults import (
    FAULT_POINTS,
    clear_fault_hooks,
    set_fault_hook,
)

from . import assert_golden, auth_for, make_service, mk_run

EXPECTED_FAULT_POINTS = (
    "after_initial_journal",
    "before_per_run_lock",
    "after_all_locks",
    "after_locked_rediscovery",
    "before_first_rename",
    "after_first_rename",
    "before_staged_lstat",
    "after_staged_lstat",
    "before_post_rename_journal",
    "before_physical_verify",
    "after_physical_verify",
    "during_delete",
    "before_cache_invalidation",
    "before_terminal_journal",
    "before_terminal_result_store",
)


def test_fault_point_registry_snapshot():
    assert FAULT_POINTS == EXPECTED_FAULT_POINTS
    assert_golden(
        "fault_point_registry.json",
        {"FAULT_POINTS": list(FAULT_POINTS)},
    )


def test_fault_points_mutation_relative_order(tmp_path: Path):
    """Existing fault points fire in the documented relative order around mutations."""
    clear_fault_hooks()
    seen: list[str] = []

    def _hook(name: str):
        def _inner() -> None:
            seen.append(name)

        return _inner

    for name in FAULT_POINTS:
        set_fault_hook(name, _hook(name))

    try:
        svc = make_service(tmp_path)
        mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
        mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000002")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "fp-order")
        result = svc.execute_cleanup(
            handle, auth_for(CleanupMode.DELETE_ALL, preview.plan_id), "fp-order"
        )
        assert result.status.value in {"SUCCESS", "PARTIAL"}
    finally:
        clear_fault_hooks()

    # Relative order among first occurrences on a two-run DELETE_ALL happy path.
    # Note: after_first_rename fires after _stage_one returns (post staged lstat /
    # post-rename journal), not immediately after the rename syscall.
    required_sequence = [
        "before_per_run_lock",
        "after_all_locks",
        "after_locked_rediscovery",
        "after_initial_journal",
        "before_first_rename",
        "before_staged_lstat",
        "after_staged_lstat",
        "before_post_rename_journal",
        "after_first_rename",
        "before_physical_verify",
        "after_physical_verify",
        "before_cache_invalidation",
        "before_terminal_journal",
        "before_terminal_result_store",
    ]
    positions = []
    for name in required_sequence:
        assert name in seen, f"fault point {name!r} did not fire; seen={seen}"
        positions.append(seen.index(name))
    assert positions == sorted(positions), f"fault order drifted: {seen}"

    # Cache invalidation must precede terminal journal (finalisation contract).
    assert seen.index("before_cache_invalidation") < seen.index(
        "before_terminal_journal"
    )
    assert seen.index("before_terminal_journal") < seen.index(
        "before_terminal_result_store"
    )

    assert_golden(
        "fault_point_happy_path_order.json",
        {"first_occurrence_order": required_sequence},
    )


def test_unknown_fault_point_rejected():
    with pytest.raises(ValueError, match="unknown fault point"):
        set_fault_hook("not_a_real_point", lambda: None)


def test_fault_point_registry_rejects_add_remove_rename_duplicate_reposition():
    """Phase A must fail characterisation if FAULT_POINTS drift in any way."""
    # Added / removed / renamed
    assert "not_a_point" not in FAULT_POINTS
    for name in EXPECTED_FAULT_POINTS:
        assert name in FAULT_POINTS
    # Duplicated
    assert len(FAULT_POINTS) == len(set(FAULT_POINTS))
    assert len(FAULT_POINTS) == len(EXPECTED_FAULT_POINTS)
    # Exact registry order frozen (reposition within the tuple fails)
    assert list(FAULT_POINTS) == list(EXPECTED_FAULT_POINTS)
    # Mutation-relative firing order is a separate freeze (not registry index order:
    # after_initial_journal is listed first in FAULT_POINTS but fires after locks).
    golden_order = [
        "before_per_run_lock",
        "after_all_locks",
        "after_locked_rediscovery",
        "after_initial_journal",
        "before_first_rename",
        "before_staged_lstat",
        "after_staged_lstat",
        "before_post_rename_journal",
        "after_first_rename",
        "before_physical_verify",
        "after_physical_verify",
        "before_cache_invalidation",
        "before_terminal_journal",
        "before_terminal_result_store",
    ]
    for name in golden_order:
        assert name in FAULT_POINTS
    # during_delete is in the registry but may not fire on every happy path
    assert "during_delete" in FAULT_POINTS
    assert_golden(
        "fault_point_mutation_relative_freeze.json",
        {
            "registry": list(FAULT_POINTS),
            "mutation_relative_first_occurrence": golden_order,
        },
    )
