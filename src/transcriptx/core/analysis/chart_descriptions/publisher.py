"""Batch publisher: attempt epoch, stage, COMMIT, ACTIVE flip, GC."""

from __future__ import annotations

import json
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from transcriptx.core.analysis.chart_descriptions.digests import sha256_file
from transcriptx.core.analysis.chart_descriptions.durable import (
    copy_file_durable,
    write_json_durable,
)
from transcriptx.core.analysis.chart_descriptions.models import (
    ActivePointer,
    AttemptEpoch,
    ChartDescriptionsIndex,
    ChartDescriptionsOutcome,
    CommitEnvelope,
)
from transcriptx.core.analysis.chart_descriptions.paths import (
    active_path,
    attempt_path,
    commit_path,
    generation_dir,
    generations_dir,
    descriptions_root,
)
from transcriptx.core.analysis.chart_descriptions.schemas import OverallStatus


def new_generation_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}_{secrets.token_hex(4)}"


def new_attempt_epoch() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}_{secrets.token_hex(6)}"


def ensure_generation_dir(run_root: Path, generation_id: str) -> Path:
    path = generation_dir(run_root, generation_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_attempt_epoch(
    run_root: Path,
    *,
    attempt_epoch: str,
    generation_id: str,
) -> Path:
    """Atomic latest-attempt tombstone written before generation work."""
    root = descriptions_root(run_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = AttemptEpoch(
        attempt_epoch=attempt_epoch,
        generation_id=generation_id,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    path = attempt_path(run_root)
    write_json_durable(path, payload.model_dump())
    return path


def read_attempt_epoch(run_root: Path) -> dict[str, Any] | None:
    path = attempt_path(run_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def write_json_under_generation(
    run_root: Path,
    generation_id: str,
    rel_path: str,
    payload: dict[str, Any],
) -> Path:
    dest = generation_dir(run_root, generation_id) / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json_durable(dest, payload)
    return dest


def write_text_under_generation(
    run_root: Path,
    generation_id: str,
    rel_path: str,
    text: str,
) -> Path:
    from transcriptx.core.analysis.chart_descriptions.durable import write_bytes_durable

    dest = generation_dir(run_root, generation_id) / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_bytes_durable(dest, text.encode("utf-8"))
    return dest


def copy_into_generation(
    run_root: Path,
    generation_id: str,
    rel_path: str,
    source: Path,
) -> Path:
    dest = generation_dir(run_root, generation_id) / rel_path
    copy_file_durable(source, dest)
    return dest


def build_commit_inventory(
    run_root: Path,
    generation_id: str,
    entries: list[dict[str, str]],
) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    gen = generation_dir(run_root, generation_id)
    for entry in entries:
        rel = entry["rel_path"]
        path = gen / rel
        inventory.append(
            {
                "rel_path": rel,
                "module": entry.get("module") or "chart_descriptions",
                "kind": entry.get("kind") or "data_json",
                "sha256": sha256_file(path) if path.is_file() else "",
            }
        )
    return inventory


def write_commit(
    run_root: Path,
    *,
    generation_id: str,
    attempt_epoch: str,
    overall_status: OverallStatus,
    inventory_snapshot_sha256: str,
    chart_set: str,
    inventory: list[dict[str, Any]],
) -> Path:
    payload = CommitEnvelope(
        generation_id=generation_id,
        attempt_epoch=attempt_epoch,
        committed_at=datetime.now(timezone.utc).isoformat(),
        overall_status=overall_status,
        inventory_snapshot_sha256=inventory_snapshot_sha256,
        chart_set=chart_set,
        artifacts=inventory,
    )
    path = commit_path(run_root, generation_id)
    write_json_durable(path, payload.model_dump())
    return path


def write_active(
    run_root: Path,
    *,
    generation_id: str,
    attempt_epoch: str,
    overall_status: OverallStatus,
    inventory_snapshot_sha256: str,
    chart_set: str,
) -> Path:
    payload = ActivePointer(
        generation_id=generation_id,
        attempt_epoch=attempt_epoch,
        overall_status=overall_status,
        committed_at=datetime.now(timezone.utc).isoformat(),
        inventory_snapshot_sha256=inventory_snapshot_sha256,
        chart_set=chart_set,
    )
    path = active_path(run_root)
    write_json_durable(path, payload.model_dump())
    return path


def read_active(run_root: Path) -> dict[str, Any] | None:
    path = active_path(run_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def active_matches_attempt(run_root: Path) -> bool:
    """Resolvers require ACTIVE.attempt_epoch == LATEST_ATTEMPT.attempt_epoch."""
    active = read_active(run_root)
    attempt = read_attempt_epoch(run_root)
    if not active or not attempt:
        return False
    return str(active.get("attempt_epoch") or "") == str(
        attempt.get("attempt_epoch") or ""
    ) and bool(active.get("generation_id"))


def read_commit(run_root: Path, generation_id: str) -> dict[str, Any] | None:
    path = commit_path(run_root, generation_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def publish_generation(
    run_root: Path,
    *,
    generation_id: str,
    attempt_epoch: str,
    overall_status: OverallStatus,
    inventory_snapshot_sha256: str,
    chart_set: str,
    index: ChartDescriptionsIndex,
    outcome: ChartDescriptionsOutcome,
    inventory_rels: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Stage index/outcome, COMMIT, flip ACTIVE. Returns prefixed manifest entries."""
    write_json_under_generation(
        run_root, generation_id, "index.json", index.model_dump()
    )
    write_json_under_generation(
        run_root, generation_id, "outcome.json", outcome.model_dump()
    )
    inventory_rels = list(inventory_rels)
    inventory_rels.extend(
        [
            {
                "rel_path": "index.json",
                "module": "chart_descriptions",
                "kind": "data_json",
            },
            {
                "rel_path": "outcome.json",
                "module": "chart_descriptions",
                "kind": "data_json",
            },
        ]
    )
    inventory = build_commit_inventory(run_root, generation_id, inventory_rels)
    write_commit(
        run_root,
        generation_id=generation_id,
        attempt_epoch=attempt_epoch,
        overall_status=overall_status,
        inventory_snapshot_sha256=inventory_snapshot_sha256,
        chart_set=chart_set,
        inventory=inventory,
    )
    write_active(
        run_root,
        generation_id=generation_id,
        attempt_epoch=attempt_epoch,
        overall_status=overall_status,
        inventory_snapshot_sha256=inventory_snapshot_sha256,
        chart_set=chart_set,
    )
    prefix = f".chart_descriptions/generations/{generation_id}/"
    return [
        {
            "rel_path": prefix + e["rel_path"],
            "module": e.get("module") or "chart_descriptions",
            "kind": e.get("kind") or "data_json",
        }
        for e in inventory_rels
    ]


def gc_uncommitted_generations(
    run_root: Path,
    *,
    keep_generation_id: str | None = None,
) -> list[str]:
    removed: list[str] = []
    root = generations_dir(run_root)
    if not root.is_dir():
        return removed
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if keep_generation_id and child.name == keep_generation_id:
            continue
        if not (child / "COMMIT.json").is_file():
            shutil.rmtree(child, ignore_errors=True)
            removed.append(child.name)
    return removed


def gc_old_committed_generations(
    run_root: Path,
    *,
    active_generation_id: str,
    retain_extra: set[str] | None = None,
) -> list[str]:
    removed: list[str] = []
    retain = set(retain_extra or ())
    retain.add(active_generation_id)
    root = generations_dir(run_root)
    if not root.is_dir():
        return removed
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name in retain:
            continue
        if (child / "COMMIT.json").is_file():
            shutil.rmtree(child, ignore_errors=True)
            removed.append(child.name)
    return removed
