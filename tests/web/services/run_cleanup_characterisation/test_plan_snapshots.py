"""Characterisation: CleanupPlan, plan ID, staging basename, execution-set signature."""

from __future__ import annotations

from pathlib import Path

from transcriptx.web.services.run_cleanup import CleanupMode
from transcriptx.web.services.run_cleanup import planning
from transcriptx.web.services.run_cleanup.plan_builder import (
    build_execution_set,
    execution_set_signature,
)
from transcriptx.web.services.run_cleanup.staging_identity import (
    collision_proof_staging_basename,
)

from . import (
    assert_golden,
    make_service,
    mk_run,
    normalise_structure,
    root_tokens,
)


def _drop_volatile_target_fields(row: dict) -> None:
    for drop in (
        "mtime_ns",
        "size_estimate_bytes",
        "file_count",
        "tree_fingerprint",
        "filesystem_dev",
        "filesystem_ino",
        "canonical_path",
    ):
        row.pop(drop, None)


def test_cleanup_plan_and_identity_snapshots(tmp_path: Path):
    svc = make_service(tmp_path)
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001", content="a")
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000002", content="b")

    plan = planning.build_plan(svc, CleanupMode.DELETE_ALL)
    roots = root_tokens(svc)
    plan_norm = normalise_structure(
        plan,
        roots=roots,
        frozen_ids={plan.plan_id: "<PLAN_ID>"},
    )
    plan_norm["created_at_iso"] = "<ISO>"
    for bucket in ("candidates", "retained"):
        for row in plan_norm.get(bucket, []):
            _drop_volatile_target_fields(row)
    for r in plan_norm.get("roots", []):
        for drop in ("dev", "ino", "canonical_path", "configured_path"):
            if drop in r:
                r[drop] = "<id>" if drop in {"dev", "ino"} else "<PATH>"
    assert_golden("plan_delete_all.json", plan_norm)

    assert_golden(
        "plan_id_delete_all.json",
        {"plan_id_token": "<PLAN_ID>", "plan_id_len": len(plan.plan_id)},
    )

    basenames = sorted(collision_proof_staging_basename(t) for t in plan.candidates)
    # Digest suffix embeds path/dev/ino/fingerprint — freeze structure only.
    structural = []
    for b in basenames:
        parts = b.rsplit("__", 1)
        structural.append(
            {
                "prefix": parts[0] if len(parts) == 2 else b,
                "digest_len": len(parts[1]) if len(parts) == 2 else 0,
            }
        )
    assert_golden(
        "staging_basenames_delete_all.json",
        {"staging_basename_structure": structural},
    )

    from transcriptx.web.services.run_cleanup.path_helpers import validate_roots

    roots_list, blocking = validate_roots(svc)
    es = build_execution_set(
        CleanupMode.DELETE_ALL,
        roots_list,
        blocking,
        svc.outputs_dir,
        svc.group_outputs_dir,
    )
    sig = execution_set_signature(es)
    assert_golden(
        "execution_set_signature_delete_all.json",
        {"signature_len": len(sig), "signature_hex": True},
    )
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)


def test_delete_old_plan_retains_newest(tmp_path: Path):
    svc = make_service(tmp_path)
    older = mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001", content="old")
    newer = mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000002", content="new")
    # Force deterministic mtimes: newer run has higher mtime.
    older.touch()
    newer.touch()

    plan = planning.build_plan(svc, CleanupMode.DELETE_OLD)
    assert len(plan.retained) == 1
    assert len(plan.candidates) == 1
    assert plan.retained[0].run_id == "20200101_000000_00000002"
    assert plan.candidates[0].run_id == "20200101_000000_00000001"

    roots = root_tokens(svc)
    plan_norm = normalise_structure(
        {
            "mode": plan.mode.value,
            "candidate_run_ids": [t.run_id for t in plan.candidates],
            "retained_run_ids": [t.run_id for t in plan.retained],
            "plan_id_len": len(plan.plan_id),
        },
        roots=roots,
    )
    assert_golden("plan_delete_old_partition.json", plan_norm)
