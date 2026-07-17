"""Phase B3: candidate cap and FD budget preflight for new operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.services.run_cleanup.locking import (
    preflight_new_operation_capacity,
)
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    MAX_CLEANUP_CANDIDATES,
    CleanupMode,
    CleanupPlan,
    CleanupTarget,
    EntryClassification,
    RootIdentity,
    SubjectType,
)


def _plan(n: int, tmp_path: Path) -> CleanupPlan:
    out = tmp_path / "outputs"
    out.mkdir(exist_ok=True)
    root = RootIdentity(
        kind=SubjectType.transcript,
        configured_path=str(out),
        canonical_path=str(out.resolve()),
        dev=1,
        ino=1,
        is_symlink=False,
    )
    targets = []
    for i in range(n):
        targets.append(
            CleanupTarget(
                subject_type=SubjectType.transcript,
                subject_id=f"s{i}",
                run_id=f"20200101_000000_{i:08d}",
                root_relative_path=f"s{i}/20200101_000000_{i:08d}",
                canonical_path=str(out / f"s{i}" / f"20200101_000000_{i:08d}"),
                mtime_ns=1,
                filesystem_dev=1,
                filesystem_ino=i + 1,
                size_estimate_bytes=1,
                file_count=1,
                tree_fingerprint="a" * 64,
                safety_status=EntryClassification.eligible,
            )
        )
    return CleanupPlan(
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="2020-01-01T00:00:00+00:00",
        roots=(root,),
        candidates=tuple(targets),
        retained=(),
        exclusions=(),
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )


@pytest.mark.unit
def test_preflight_rejects_over_candidate_cap(tmp_path: Path) -> None:
    plan = _plan(MAX_CLEANUP_CANDIDATES + 1, tmp_path)
    err = preflight_new_operation_capacity(plan)
    assert err is not None
    assert "too many cleanup candidates" in err


@pytest.mark.unit
def test_preflight_accepts_small_plan(tmp_path: Path) -> None:
    plan = _plan(2, tmp_path)
    assert preflight_new_operation_capacity(plan) is None


@pytest.mark.unit
def test_preflight_rejects_when_fd_budget_exceeds_soft_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(8, tmp_path)

    def tiny_limit(_resource: int):
        return (16, 16)

    monkeypatch.setattr("resource.getrlimit", tiny_limit)
    err = preflight_new_operation_capacity(plan)
    assert err is not None
    assert "RLIMIT_NOFILE" in err


@pytest.mark.unit
def test_preflight_refuses_when_getrlimit_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(2, tmp_path)

    def boom(_resource: int):
        raise OSError("no rlimit")

    monkeypatch.setattr("resource.getrlimit", boom)
    err = preflight_new_operation_capacity(plan)
    assert err is not None
    assert "RLIMIT_NOFILE" in err


@pytest.mark.unit
def test_preflight_refuses_nonpositive_soft_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(2, tmp_path)
    monkeypatch.setattr("resource.getrlimit", lambda _r: (0, 0))
    err = preflight_new_operation_capacity(plan)
    assert err is not None
    assert "invalid process FD limit" in err
