"""Characterisation: side-effect counts and sequences for Phase A parity."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from transcriptx.web.services.run_cleanup import CleanupMode, CleanupStatus
from transcriptx.web.services.run_cleanup import journal as cleanup_journal

from . import assert_golden, auth_for, make_service, mk_run


class CountLog:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.order: list[str] = []

    def wrap(self, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            self.counts[name] = self.counts.get(name, 0) + 1
            self.order.append(name)
            return fn(*args, **kwargs)

        return _wrapped


def test_execute_side_effect_counts_delete_all(tmp_path: Path, monkeypatch):
    log = CountLog()
    from transcriptx.web.services.run_cleanup import handles as handle_store
    from transcriptx.web.services.run_cleanup import locking as locking_mod

    monkeypatch.setattr(
        cleanup_journal,
        "write_operation",
        log.wrap("journal_write_operation", cleanup_journal.write_operation),
    )
    monkeypatch.setattr(
        cleanup_journal,
        "update_target_state",
        log.wrap("journal_update_target", cleanup_journal.update_target_state),
    )
    monkeypatch.setattr(
        cleanup_journal,
        "update_operation_status",
        log.wrap("journal_update_status", cleanup_journal.update_operation_status),
    )
    monkeypatch.setattr(
        handle_store,
        "claim_handle",
        log.wrap("handle_claim", handle_store.claim_handle),
    )
    monkeypatch.setattr(
        handle_store,
        "store_result",
        log.wrap("handle_store_result", handle_store.store_result),
    )
    monkeypatch.setattr(
        locking_mod,
        "try_per_run_lock",
        log.wrap("lock_acquire", locking_mod.try_per_run_lock),
    )

    cache_n = {"n": 0}

    def _cache() -> None:
        cache_n["n"] += 1
        log.order.append("cache_invalidate")
        log.counts["cache_invalidate"] = log.counts.get("cache_invalidate", 0) + 1

    svc = make_service(tmp_path, cache_invalidator=_cache)
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000002")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "parity-session")
    result = svc.execute_cleanup(
        handle,
        auth_for(CleanupMode.DELETE_ALL, preview.plan_id),
        "parity-session",
    )
    assert result.status is CleanupStatus.SUCCESS

    # Prefer locking-module lock spy (running code imports try_per_run_lock there).
    lock_count = log.counts.get("lock_acquire", 0)
    payload = {
        "status": result.status.value,
        "journal_write_operation": log.counts.get("journal_write_operation", 0),
        "journal_update_status": log.counts.get("journal_update_status", 0),
        "handle_claim": log.counts.get("handle_claim", 0),
        "handle_store_result": log.counts.get("handle_store_result", 0),
        "cache_invalidate": cache_n["n"],
        "lock_acquire": lock_count,
        "target_count": len(result.targets),
        "visible_removed": result.visible_removed_count,
        "physically_deleted": result.physically_deleted_count,
    }
    assert payload["journal_write_operation"] == 1
    assert payload["journal_update_status"] == 1
    assert payload["handle_claim"] == 1
    assert payload["handle_store_result"] == 1
    assert payload["cache_invalidate"] == 1
    assert payload["lock_acquire"] == 2
    # Cache before terminal journal status update.
    assert log.order.index("cache_invalidate") < log.order.index(
        "journal_update_status"
    )
    assert_golden("side_effect_counts_delete_all.json", payload)


def test_lock_skip_target_ordering(tmp_path: Path, monkeypatch):
    """When one run lock fails, LOCKED_SKIP appears with PARTIAL status."""
    from transcriptx.web.services.run_cleanup import locking as locking_mod
    from transcriptx.core.utils.run_writer_locks import try_per_run_lock as real_try

    svc = make_service(tmp_path)
    r1 = mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000002")
    blocked = str(r1.resolve())

    def _selective(canonical_run_root, *, state_dir=None):
        from transcriptx.core.utils.path_canonical import canonicalise_path

        canon = str(canonicalise_path(canonical_run_root))
        if canon == blocked or str(canonical_run_root) == blocked:
            return None
        return real_try(canonical_run_root, state_dir=state_dir)

    monkeypatch.setattr(locking_mod, "try_per_run_lock", _selective)

    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "lock-skip")
    result = svc.execute_cleanup(
        handle,
        auth_for(CleanupMode.DELETE_ALL, preview.plan_id),
        "lock-skip",
    )

    assert result.status is CleanupStatus.PARTIAL
    statuses = [t.status.value for t in result.targets]
    assert "LOCKED_SKIP" in statuses
    assert "PHYSICAL_DELETED" in statuses
    ordered = [
        {"run_id": t.run_id, "status": t.status.value}
        for t in result.targets
        if t.status.value in {"LOCKED_SKIP", "PHYSICAL_DELETED", "VISIBLE_REMOVED"}
    ]
    assert_golden(
        "lock_skip_target_statuses.json",
        {
            "status": result.status.value,
            "targets": sorted(ordered, key=lambda r: (r["run_id"], r["status"])),
        },
    )


def test_coded_error_logger_severity_gate_busy(tmp_path: Path, caplog, monkeypatch):
    from transcriptx.web.services.run_cleanup import execution as execution_mod

    svc = make_service(tmp_path)
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "busy-log")

    monkeypatch.setattr(execution_mod, "try_run_tree_mutation_gate", lambda **kw: None)

    with caplog.at_level(logging.WARNING):
        result = svc.execute_cleanup(
            handle,
            auth_for(CleanupMode.DELETE_ALL, preview.plan_id),
            "busy-log",
        )

    assert result.status is CleanupStatus.BLOCKED
    assert any("CLEANUP_BUSY" in e for e in result.errors)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("mutation gate busy" in r.getMessage() for r in warnings)
    assert_golden(
        "coded_error_gate_busy_log.json",
        {
            "status": result.status.value,
            "errors": list(result.errors),
            "warning_message_substr": "mutation gate busy",
        },
    )
