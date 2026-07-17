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

    def test_all_external_disappeared_success(self) -> None:
        assert (
            results_mod.status_from_journal_targets(
                [{"state": "external_disappeared"}, {"state": "external_disappeared"}]
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
def test_phase_a_policy_and_schema_frozen() -> None:
    """Literal freeze — goldens alone do not pin the constants if regenerated."""
    assert CLEANUP_POLICY_VERSION == 4
    assert JOURNAL_SCHEMA_VERSION == 3
