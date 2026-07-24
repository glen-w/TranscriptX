"""Phase B R1: journal RMW lock is distinct from claim and serializes updates."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    JOURNAL_SCHEMA_VERSION,
    CleanupMode,
    CleanupPlan,
    CleanupTarget,
    EntryClassification,
    RootIdentity,
    SubjectType,
)


def _write_op(state: Path, out: Path) -> tuple[str, CleanupTarget]:
    out.mkdir(parents=True, exist_ok=True)
    run = out / "slug" / "20200101_000000_00000001"
    run.mkdir(parents=True)
    (run / "f.txt").write_text("x", encoding="utf-8")
    st = run.lstat()
    target = CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="slug",
        run_id="20200101_000000_00000001",
        root_relative_path="slug/20200101_000000_00000001",
        canonical_path=str(run.resolve()),
        mtime_ns=st.st_mtime_ns,
        filesystem_dev=int(st.st_dev),
        filesystem_ino=int(st.st_ino),
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint="a" * 64,
        safety_status=EntryClassification.eligible,
    )
    root = RootIdentity(
        kind=SubjectType.transcript,
        configured_path=str(out),
        canonical_path=str(out.resolve()),
        dev=int(out.lstat().st_dev),
        ino=int(out.lstat().st_ino),
        is_symlink=False,
    )
    plan = CleanupPlan(
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="2020-01-01T00:00:00+00:00",
        roots=(root,),
        candidates=(target,),
        retained=(),
        exclusions=(),
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )
    oid = "1_abcdefabcdef"
    journal.write_operation(state, operation_id=oid, plan=plan)
    return oid, target


@pytest.mark.unit
def test_rmw_and_claim_lock_paths_are_distinct(tmp_path: Path) -> None:
    oid = "1_abcdefabcdef"
    claim = journal.journal_claim_lock_path(tmp_path, oid)
    rmw = journal.journal_rmw_lock_path(tmp_path, oid)
    assert claim != rmw
    assert claim.name.endswith(".claim.lock")
    assert rmw.name.endswith(".rmw.lock")


@pytest.mark.unit
def test_update_target_state_under_rmw_lock(tmp_path: Path) -> None:
    state = tmp_path / "state"
    out = tmp_path / "outputs"
    oid, target = _write_op(state, out)
    dur = journal.update_target_state(
        state,
        oid,
        canonical_path=target.canonical_path,
        state="staged",
        staging_path="/tmp/staged",
    )
    assert dur.outcome is journal.DirFsyncOutcome.OK
    data = journal.load_operation(
        state,
        oid,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert data is not None
    assert data["targets"][0]["state"] == "staged"


@pytest.mark.unit
def test_claim_uses_unlocked_status_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Claim must not call public update_operation_status (would nest locks)."""
    state = tmp_path / "state"
    out = tmp_path / "outputs"
    oid, _target = _write_op(state, out)
    journal.update_operation_status(state, oid, "PARTIAL")

    called_public = {"n": 0}
    real_public = journal.update_operation_status

    def boom(*_a, **_k):
        called_public["n"] += 1
        raise AssertionError(
            "public update_operation_status must not be used from claim"
        )

    monkeypatch.setattr(journal, "update_operation_status", boom)
    dur = journal.claim_retry_ownership(state, oid)
    assert dur.outcome is journal.DirFsyncOutcome.OK
    assert called_public["n"] == 0
    # restore not needed — test ends
    _ = real_public
