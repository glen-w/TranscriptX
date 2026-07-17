"""Characterisation: collaborator spy ordering around execute phases."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from transcriptx.web.services.run_cleanup import CleanupMode
from transcriptx.web.services.run_cleanup import journal as cleanup_journal
from transcriptx.web.services.run_cleanup.faults import (
    clear_fault_hooks,
    set_fault_hook,
)

from . import assert_golden, auth_for, make_service, mk_run


class EventLog:
    def __init__(self) -> None:
        self.events: list[str] = []

    def record(self, name: str) -> None:
        self.events.append(name)

    def wrap(self, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            self.record(name)
            return fn(*args, **kwargs)

        return _wrapped


def test_execute_phase_order_with_spies(tmp_path: Path, monkeypatch):
    """Test-side spies (no new production hooks) characterise phase order."""
    log = EventLog()
    clear_fault_hooks()

    # Fault points as coarse markers already in production.
    for name in (
        "after_initial_journal",
        "before_first_rename",
        "before_physical_verify",
        "before_cache_invalidation",
        "before_terminal_journal",
        "before_terminal_result_store",
    ):
        set_fault_hook(name, lambda n=name: log.record(f"fault:{n}"))

    # Collaborator spies — patch at the modules the running code imports from.
    from transcriptx.web.services.run_cleanup import execution as execution_mod
    from transcriptx.web.services.run_cleanup import handles as handle_store
    from transcriptx.web.services.run_cleanup import staging_phase
    from transcriptx.web.services.run_cleanup import fd_ops

    monkeypatch.setattr(
        execution_mod,
        "try_run_tree_mutation_gate",
        log.wrap("gate_acquire", execution_mod.try_run_tree_mutation_gate),
    )
    monkeypatch.setattr(
        handle_store,
        "claim_handle",
        log.wrap("handle_claim", handle_store.claim_handle),
    )
    monkeypatch.setattr(
        fd_ops,
        "platform_supports_secure_cleanup",
        log.wrap(
            "platform_check",
            fd_ops.platform_supports_secure_cleanup,
        ),
    )
    monkeypatch.setattr(
        staging_phase,
        "ensure_secure_staging_directory",
        log.wrap(
            "staging_dir_provision",
            staging_phase.ensure_secure_staging_directory,
        ),
    )
    monkeypatch.setattr(
        execution_mod,
        "ensure_secure_staging_directory",
        log.wrap(
            "staging_dir_provision",
            execution_mod.ensure_secure_staging_directory,
        ),
    )
    monkeypatch.setattr(
        staging_phase,
        "rename_into_staging",
        log.wrap("rename", staging_phase.rename_into_staging),
    )
    monkeypatch.setattr(
        cleanup_journal,
        "write_operation",
        log.wrap("journal_write_operation", cleanup_journal.write_operation),
    )
    monkeypatch.setattr(
        cleanup_journal,
        "update_operation_status",
        log.wrap(
            "journal_terminal_status",
            cleanup_journal.update_operation_status,
        ),
    )
    monkeypatch.setattr(
        handle_store,
        "store_result",
        log.wrap("handle_store_result", handle_store.store_result),
    )

    cache_calls = {"n": 0}

    def _cache() -> None:
        cache_calls["n"] += 1
        log.record("cache_invalidate")

    try:
        svc = make_service(tmp_path, cache_invalidator=_cache)
        mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "order-session")
        result = svc.execute_cleanup(
            handle,
            auth_for(CleanupMode.DELETE_ALL, preview.plan_id),
            "order-session",
        )
        assert result.status.value in {"SUCCESS", "PARTIAL"}
        assert cache_calls["n"] == 1
    finally:
        clear_fault_hooks()

    events = log.events

    def idx(name: str) -> int:
        assert name in events, f"missing event {name!r} in {events}"
        return events.index(name)

    # Core ordering contract (plan § ordering).
    assert idx("gate_acquire") < idx("handle_claim")
    assert idx("handle_claim") < idx("platform_check")
    assert idx("journal_write_operation") < idx("staging_dir_provision")
    assert idx("fault:after_initial_journal") < idx("staging_dir_provision")
    assert idx("staging_dir_provision") < idx("rename")
    assert idx("fault:before_first_rename") <= idx("rename")
    assert idx("rename") < idx("fault:before_physical_verify")
    assert idx("cache_invalidate") < idx("journal_terminal_status")
    assert idx("fault:before_cache_invalidation") < idx("fault:before_terminal_journal")
    assert idx("journal_terminal_status") < idx("handle_store_result")
    assert idx("fault:before_terminal_result_store") <= idx("handle_store_result")

    # Coarse golden of first occurrences (stable subsequence).
    firsts = []
    for name in (
        "gate_acquire",
        "handle_claim",
        "platform_check",
        "journal_write_operation",
        "fault:after_initial_journal",
        "staging_dir_provision",
        "rename",
        "fault:before_physical_verify",
        "cache_invalidate",
        "journal_terminal_status",
        "handle_store_result",
    ):
        firsts.append(name)
        assert name in events
    positions = [events.index(n) for n in firsts]
    assert positions == sorted(positions)
    assert_golden("execute_phase_order_firsts.json", {"firsts": firsts})
