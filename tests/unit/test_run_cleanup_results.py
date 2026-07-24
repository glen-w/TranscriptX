"""Unit tests for run_cleanup results status reduction (Phase A extract)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.services.run_cleanup import results as results_mod
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    JOURNAL_SCHEMA_VERSION,
    CleanupStatus,
)


@pytest.mark.unit
class TestSummarizeStatus:
    def test_mutation_full_success(self) -> None:
        assert (
            results_mod.summarize_status(
                visible_removed=2,
                physically_deleted=2,
                planned=2,
                lock_skips=0,
                errors=[],
                has_staged_remnant=False,
                mutation_started=True,
            )
            is CleanupStatus.SUCCESS
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"errors": ["x"]},
            {"has_staged_remnant": True},
            {"lock_skips": 1},
            {"visible_removed": 1, "physically_deleted": 2, "planned": 2},
            {"visible_removed": 2, "physically_deleted": 1, "planned": 2},
        ],
    )
    def test_mutation_partial(self, kwargs: dict) -> None:
        base = {
            "visible_removed": 2,
            "physically_deleted": 2,
            "planned": 2,
            "lock_skips": 0,
            "errors": [],
            "has_staged_remnant": False,
            "mutation_started": True,
        }
        base.update(kwargs)
        assert results_mod.summarize_status(**base) is CleanupStatus.PARTIAL

    def test_no_mutation_lock_skips_partial(self) -> None:
        assert (
            results_mod.summarize_status(
                visible_removed=0,
                physically_deleted=0,
                planned=2,
                lock_skips=1,
                errors=[],
                has_staged_remnant=False,
                mutation_started=False,
            )
            is CleanupStatus.PARTIAL
        )

    def test_no_mutation_errors_failed_before(self) -> None:
        assert (
            results_mod.summarize_status(
                visible_removed=0,
                physically_deleted=0,
                planned=1,
                lock_skips=0,
                errors=["boom"],
                has_staged_remnant=False,
                mutation_started=False,
            )
            is CleanupStatus.FAILED_BEFORE_MUTATION
        )

    def test_noop(self) -> None:
        assert (
            results_mod.summarize_status(
                visible_removed=0,
                physically_deleted=0,
                planned=0,
                lock_skips=0,
                errors=[],
                has_staged_remnant=False,
                mutation_started=False,
            )
            is CleanupStatus.NOOP
        )


@pytest.mark.unit
class TestStatusFromJournalTargets:
    def test_empty_noop(self) -> None:
        assert results_mod.status_from_journal_targets([]) is CleanupStatus.NOOP

    def test_all_skips_noop(self) -> None:
        assert (
            results_mod.status_from_journal_targets(
                [{"state": "locked_skip"}, {"state": "staging_failed"}]
            )
            is CleanupStatus.NOOP
        )

    def test_planned_plus_success_partial(self) -> None:
        assert (
            results_mod.status_from_journal_targets(
                [{"state": "planned"}, {"state": "physical_deleted"}]
            )
            is CleanupStatus.PARTIAL
        )

    def test_all_external_disappeared_partial(self) -> None:
        assert (
            results_mod.status_from_journal_targets(
                [{"state": "external_disappeared"}, {"state": "external_disappeared"}]
            )
            is CleanupStatus.PARTIAL
        )

    def test_deleted_plus_lock_skip_partial(self) -> None:
        assert (
            results_mod.status_from_journal_targets(
                [{"state": "physical_deleted"}, {"state": "locked_skip"}]
            )
            is CleanupStatus.PARTIAL
        )

    def test_all_physical_deleted_success(self) -> None:
        assert (
            results_mod.status_from_journal_targets(
                [{"state": "physical_deleted"}, {"state": "physical_deleted"}]
            )
            is CleanupStatus.SUCCESS
        )

    def test_unknown_state_partial(self) -> None:
        assert (
            results_mod.status_from_journal_targets([{"state": "not_a_real_state"}])
            is CleanupStatus.PARTIAL
        )

    def test_missing_or_empty_state_partial(self) -> None:
        assert (
            results_mod.status_from_journal_targets([{"state": None}])
            is CleanupStatus.PARTIAL
        )
        assert (
            results_mod.status_from_journal_targets([{"state": ""}])
            is CleanupStatus.PARTIAL
        )
        assert results_mod.status_from_journal_targets([{}]) is CleanupStatus.PARTIAL


@pytest.mark.unit
def test_status_from_loaded_operation_missing(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    with pytest.raises(FileNotFoundError, match="cleanup journal missing"):
        results_mod.status_from_loaded_operation(state, "1_abcdefabcdef")


@pytest.mark.unit
def test_status_from_loaded_operation_success_vector(tmp_path: Path) -> None:
    from transcriptx.web.services.run_cleanup import journal as journal_mod
    from transcriptx.web.services.run_cleanup.models import (
        CleanupMode,
        CleanupPlan,
        CleanupTarget,
        EntryClassification,
        RootIdentity,
        SubjectType,
    )

    state = tmp_path / "state"
    state.mkdir()
    out = tmp_path / "outputs"
    out.mkdir()
    run = out / "s" / "20200101_000000_00000001"
    run.mkdir(parents=True)
    target = CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="s",
        run_id="20200101_000000_00000001",
        root_relative_path="s/20200101_000000_00000001",
        canonical_path=str(run.resolve()),
        mtime_ns=1,
        filesystem_dev=1,
        filesystem_ino=1,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint="a" * 64,
        safety_status=EntryClassification.eligible,
    )
    root_st = out.lstat()
    plan = CleanupPlan(
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="t",
        roots=(
            RootIdentity(
                kind=SubjectType.transcript,
                configured_path=str(out),
                canonical_path=str(out.resolve()),
                dev=root_st.st_dev,
                ino=root_st.st_ino,
                is_symlink=False,
            ),
        ),
        candidates=(target,),
        retained=(),
        exclusions=(),
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )
    oid = journal_mod.new_operation_id()
    dest = journal_mod.intended_staging_path(out, oid, target)
    journal_mod.write_operation(
        state,
        operation_id=oid,
        plan=plan,
        staging_destinations={target.canonical_path: str(dest)},
    )
    journal_mod.update_target_state(
        state,
        oid,
        canonical_path=target.canonical_path,
        state="physical_deleted",
        staging_path=str(dest),
    )
    assert results_mod.status_from_loaded_operation(state, oid) is CleanupStatus.SUCCESS


@pytest.mark.unit
def test_phase_b_policy_and_schema() -> None:
    assert CLEANUP_POLICY_VERSION == 7
    assert JOURNAL_SCHEMA_VERSION == 1
