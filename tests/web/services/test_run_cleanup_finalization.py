"""Integration: finalization SUCCESS demotion and cache-before-terminal order."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.web.services.run_cleanup import finalization
from transcriptx.web.services.run_cleanup import handles as handle_store
from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup import results as results_mod
from transcriptx.web.services.run_cleanup.models import (
    CleanupMode,
    CleanupResult,
    CleanupStatus,
)


def _success_result(*, operation_id: str = "1_abcdefabcdef") -> CleanupResult:
    return CleanupResult(
        operation_id=operation_id,
        plan_id="plan",
        mode=CleanupMode.DELETE_ALL,
        status=CleanupStatus.SUCCESS,
        targets=(),
        warnings=(),
        errors=(),
        visible_removed_count=1,
        physically_deleted_count=1,
    )


@pytest.mark.unit
def test_finalise_demotes_success_when_loaded_status_diverges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never write SUCCESS if re-derived journal vector is not SUCCESS."""
    state = tmp_path / "state"
    state.mkdir()
    order: list[str] = []

    host = SimpleNamespace(
        state_dir=state,
        _cache_invalidator=lambda: order.append("cache"),
    )

    monkeypatch.setattr(
        results_mod,
        "status_from_loaded_operation",
        lambda _state_dir, _oid: (
            order.append("derive"),
            CleanupStatus.PARTIAL,
        )[1],
    )

    def update_status(_state, _oid, status_value: str):
        order.append(f"terminal:{status_value}")
        return journal.DirFsyncResult(journal.DirFsyncOutcome.OK)

    monkeypatch.setattr(journal, "update_operation_status", update_status)
    monkeypatch.setattr(
        handle_store,
        "store_result",
        lambda *_a, **_k: order.append("store"),
    )

    final = finalization.finalise_operation(
        host,
        handle_token="tok",
        session_id="sess",
        result=_success_result(),
        operation_id="1_abcdefabcdef",
        mutation_started=True,
    )
    assert final.status is CleanupStatus.PARTIAL
    assert order == ["cache", "derive", "terminal:PARTIAL", "store"]


@pytest.mark.unit
def test_finalise_demotes_on_terminal_fsync_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    host = SimpleNamespace(state_dir=state, _cache_invalidator=None)
    monkeypatch.setattr(
        results_mod,
        "status_from_loaded_operation",
        lambda *_a, **_k: CleanupStatus.SUCCESS,
    )
    monkeypatch.setattr(
        journal,
        "update_operation_status",
        lambda *_a, **_k: journal.DirFsyncResult(
            journal.DirFsyncOutcome.FAILED, "dir fsync failed"
        ),
    )
    monkeypatch.setattr(handle_store, "store_result", lambda *_a, **_k: None)
    # Avoid real artifact/listing cache imports when invalidator is None.
    monkeypatch.setattr(finalization, "invalidate_caches", lambda _host: [])

    final = finalization.finalise_operation(
        host,
        handle_token="tok",
        session_id="sess",
        result=_success_result(),
        operation_id="1_abcdefabcdef",
        mutation_started=True,
    )
    assert final.status is CleanupStatus.PARTIAL
    assert any("terminal journal durability failed" in e for e in final.errors)


@pytest.mark.unit
def test_finalise_skips_cache_when_no_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    called = {"cache": 0}

    def _cache(_host) -> list[str]:
        called["cache"] += 1
        return []

    host = SimpleNamespace(state_dir=state, _cache_invalidator=None)
    monkeypatch.setattr(finalization, "invalidate_caches", _cache)
    monkeypatch.setattr(
        journal,
        "update_operation_status",
        lambda *_a, **_k: journal.DirFsyncResult(journal.DirFsyncOutcome.OK),
    )
    monkeypatch.setattr(handle_store, "store_result", lambda *_a, **_k: None)

    final = finalization.finalise_operation(
        host,
        handle_token="tok",
        session_id="sess",
        result=_success_result(operation_id=""),
        operation_id="",
        mutation_started=False,
    )
    assert called["cache"] == 0
    assert final.status is CleanupStatus.SUCCESS
