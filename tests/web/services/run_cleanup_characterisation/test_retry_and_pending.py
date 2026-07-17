"""Characterisation: list_pending_staging and retry_interrupted_staging."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.web.services.run_cleanup import CleanupMode, CleanupStatus
from transcriptx.web.services.run_cleanup import journal as cleanup_journal
from transcriptx.web.services.run_cleanup.faults import (
    clear_fault_hooks,
    set_fault_hook,
)
from transcriptx.web.services.run_cleanup.models import result_as_dict

from . import (
    assert_golden,
    auth_for,
    make_service,
    mk_run,
    normalise_structure,
    root_tokens,
)

# Must match OPERATION_ID_RE: ^[0-9]+_[0-9a-f]{12}$
_FROZEN_OP_ID = "2000000000_abcdef123456"


def test_list_pending_after_interrupted_staging(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cleanup_journal, "new_operation_id", lambda: _FROZEN_OP_ID)
    clear_fault_hooks()
    set_fault_hook(
        "after_first_rename",
        lambda: (_ for _ in ()).throw(RuntimeError("inject")),
    )

    svc = make_service(tmp_path)
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "pending-session")
    try:
        result = svc.execute_cleanup(
            handle,
            auth_for(CleanupMode.DELETE_ALL, preview.plan_id),
            "pending-session",
        )
    finally:
        clear_fault_hooks()

    assert result.status is CleanupStatus.PARTIAL
    assert result.operation_id == _FROZEN_OP_ID
    pending = svc.list_pending_staging()
    assert pending, "expected pending staging after interrupted execute"
    roots = root_tokens(svc)
    pending_norm = normalise_structure(
        pending,
        roots=roots,
        frozen_ids={
            preview.plan_id: "<PLAN_ID>",
            _FROZEN_OP_ID: "<OPERATION_ID>",
        },
    )
    for row in pending_norm:
        for drop in (
            "updated_at",
            "created_at",
            "completed_at",
            "filesystem_dev",
            "filesystem_ino",
            "staged_dev",
            "staged_ino",
            "tree_fingerprint",
            "canonical_path",
            "staging_path",
            "root_relative_path",
        ):
            row.pop(drop, None)
    assert_golden("list_pending_interrupted.json", pending_norm)


def test_retry_interrupted_completes_and_orders_targets(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cleanup_journal, "new_operation_id", lambda: _FROZEN_OP_ID)
    clear_fault_hooks()
    set_fault_hook(
        "after_first_rename",
        lambda: (_ for _ in ()).throw(RuntimeError("inject")),
    )

    svc = make_service(tmp_path)
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "retry-session")
    try:
        interrupted = svc.execute_cleanup(
            handle,
            auth_for(CleanupMode.DELETE_ALL, preview.plan_id),
            "retry-session",
        )
    finally:
        clear_fault_hooks()

    assert interrupted.status is CleanupStatus.PARTIAL
    assert interrupted.operation_id == _FROZEN_OP_ID

    retry = svc.retry_interrupted_staging(interrupted.operation_id)
    assert retry.status in {
        CleanupStatus.SUCCESS,
        CleanupStatus.PARTIAL,
        CleanupStatus.NOOP,
    }
    assert retry.operation_id == interrupted.operation_id

    roots = root_tokens(svc)
    retry_norm = normalise_structure(
        result_as_dict(retry),
        roots=roots,
        frozen_ids={
            preview.plan_id: "<PLAN_ID>",
            interrupted.operation_id: "<OPERATION_ID>",
        },
    )
    for t in retry_norm.get("targets", []):
        for drop in ("filesystem_dev", "filesystem_ino", "staging_path", "message"):
            t.pop(drop, None)
    retry_norm["targets"] = sorted(
        retry_norm.get("targets", []),
        key=lambda t: (t.get("run_id") or "", t.get("status") or ""),
    )
    assert_golden("retry_interrupted_result.json", retry_norm)

    op_path = (
        cleanup_journal.operations_dir(svc.state_dir)
        / f"{interrupted.operation_id}.json"
    )
    data = json.loads(op_path.read_text(encoding="utf-8"))
    assert data.get("status") not in {None, "running", "planned"}
