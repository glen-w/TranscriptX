"""Characterisation: happy-path goldens for preview / result / journal."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.web.services.run_cleanup import CleanupMode, CleanupStatus
from transcriptx.web.services.run_cleanup import journal as cleanup_journal
from transcriptx.web.services.run_cleanup.models import result_as_dict

from . import (
    assert_golden,
    auth_for,
    make_service,
    mk_run,
    normalise_structure,
    root_tokens,
)


def test_delete_all_happy_path_goldens(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        cleanup_journal, "new_operation_id", lambda: "1000000000_abcdef123456"
    )

    cache_n = {"n": 0}

    def _cache() -> None:
        cache_n["n"] += 1

    svc = make_service(tmp_path, cache_invalidator=_cache)
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001", content="a")
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000002", content="b")

    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "golden-session")
    assert preview.can_execute
    assert preview.run_count == 2

    roots = root_tokens(svc)
    preview_norm = normalise_structure(
        preview,
        roots=roots,
        frozen_ids={preview.plan_id: "<PLAN_ID>"},
    )
    for bucket in ("candidates", "retained"):
        for row in preview_norm.get(bucket, []):
            for drop in (
                "mtime_ns",
                "size_estimate_bytes",
                "file_count",
                "tree_fingerprint",
                "filesystem_dev",
                "filesystem_ino",
            ):
                row.pop(drop, None)
    preview_norm["file_count"] = "<omitted>"
    preview_norm["size_estimate_bytes"] = "<omitted>"
    assert_golden("preview_delete_all.json", preview_norm)

    result = svc.execute_cleanup(
        handle,
        auth_for(CleanupMode.DELETE_ALL, preview.plan_id),
        "golden-session",
    )
    assert result.status is CleanupStatus.SUCCESS
    assert result.operation_id == "1000000000_abcdef123456"
    assert cache_n["n"] == 1

    result_norm = normalise_structure(
        result_as_dict(result),
        roots=roots,
        frozen_ids={
            preview.plan_id: "<PLAN_ID>",
            result.operation_id: "<OPERATION_ID>",
        },
    )
    for t in result_norm.get("targets", []):
        for drop in ("filesystem_dev", "filesystem_ino", "staging_path"):
            t.pop(drop, None)
        msg = t.get("message")
        if isinstance(msg, str) and msg:
            from . import normalise_path_text

            t["message"] = normalise_path_text(msg, roots)
    assert_golden("result_delete_all_success.json", result_norm)

    op_path = (
        cleanup_journal.operations_dir(svc.state_dir) / f"{result.operation_id}.json"
    )
    raw = op_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    journal_norm = normalise_structure(
        data,
        roots=roots,
        frozen_ids={
            preview.plan_id: "<PLAN_ID>",
            result.operation_id: "<OPERATION_ID>",
        },
    )
    for drop in ("created_at", "updated_at", "completed_at"):
        journal_norm.pop(drop, None)
    for t in journal_norm.get("targets", []):
        for drop in (
            "tree_fingerprint",
            "filesystem_dev",
            "filesystem_ino",
            "staged_dev",
            "staged_ino",
            "staging_path",
        ):
            t.pop(drop, None)
    for r in journal_norm.get("roots", []):
        for drop in ("dev", "ino", "canonical_path", "configured_path"):
            if drop in r:
                r[drop] = "<id>" if drop in {"dev", "ino"} else r[drop]
    assert_golden("journal_delete_all_terminal.json", journal_norm)


def test_auth_rejection_characterisation(tmp_path: Path):
    svc = make_service(tmp_path)
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "auth-session")
    bad = auth_for(CleanupMode.DELETE_ALL, preview.plan_id)
    bad = type(bad)(
        acknowledged=True,
        phrase="DELETE ALL ",  # trailing space — exact match required
        mode=CleanupMode.DELETE_ALL,
        plan_id=preview.plan_id,
    )
    result = svc.execute_cleanup(handle, bad, "auth-session")
    assert result.status.value == "BLOCKED"
    assert any("Authorization failed" in e for e in result.errors)
    roots = root_tokens(svc)
    payload = normalise_structure(
        result_as_dict(result),
        roots=roots,
        frozen_ids={preview.plan_id: "<PLAN_ID>"},
    )
    assert_golden("result_auth_blocked.json", payload)


def test_stale_plan_characterisation(tmp_path: Path):
    svc = make_service(tmp_path)
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "stale-session")
    # Mutate tree after preview → plan_id mismatch on rediscovery.
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000002")
    result = svc.execute_cleanup(
        handle,
        auth_for(CleanupMode.DELETE_ALL, preview.plan_id),
        "stale-session",
    )
    assert result.status.value == "STALE_PLAN"
    roots = root_tokens(svc)
    payload = normalise_structure(
        result_as_dict(result),
        roots=roots,
        frozen_ids={preview.plan_id: "<PLAN_ID>"},
    )
    assert_golden("result_stale_plan.json", payload)
