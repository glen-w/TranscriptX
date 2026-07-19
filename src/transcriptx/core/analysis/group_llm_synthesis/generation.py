"""Generation staging, COMMIT, ACTIVE pointer, and GC."""

from __future__ import annotations

import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from transcriptx.core.analysis.group_llm_synthesis.digests import (
    InputDigests,
    sha256_file,
)
from transcriptx.core.analysis.group_llm_synthesis.durable import (
    write_bytes_durable,
    write_json_durable,
)
from transcriptx.core.analysis.group_llm_synthesis.paths import (
    active_path,
    commit_path,
    generation_dir,
    generations_dir,
)
from transcriptx.core.analysis.group_llm_synthesis.schemas import (
    SCHEMA_ACTIVE,
    SCHEMA_COMMIT,
    OverallStatus,
)


def new_generation_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}_{secrets.token_hex(4)}"


def ensure_generation_dir(run_root: Path, generation_id: str) -> Path:
    path = generation_dir(run_root, generation_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text_under_generation(
    run_root: Path,
    generation_id: str,
    rel_path: str,
    text: str,
) -> Path:
    dest = generation_dir(run_root, generation_id) / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_bytes_durable(dest, text.encode("utf-8"))
    return dest


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


def build_commit_inventory(
    run_root: Path,
    generation_id: str,
    entries: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """entries: {rel_path, module, kind} — digests computed from disk."""
    inventory: list[dict[str, Any]] = []
    gen = generation_dir(run_root, generation_id)
    for entry in entries:
        rel = entry["rel_path"]
        path = gen / rel
        inventory.append(
            {
                "rel_path": rel,
                "module": entry["module"],
                "kind": entry["kind"],
                "sha256": sha256_file(path) if path.is_file() else "",
            }
        )
    return inventory


def write_commit(
    run_root: Path,
    *,
    generation_id: str,
    digests: InputDigests,
    overall_status: OverallStatus,
    inventory: list[dict[str, Any]],
) -> Path:
    payload = {
        "schema_id": SCHEMA_COMMIT,
        "generation_id": generation_id,
        "committed_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        **digests.as_dict(),
        "artifacts": inventory,
    }
    path = commit_path(run_root, generation_id)
    write_json_durable(path, payload)
    return path


def write_active(
    run_root: Path,
    *,
    generation_id: str,
    digests: InputDigests,
    overall_status: OverallStatus,
) -> Path:
    payload = {
        "schema_id": SCHEMA_ACTIVE,
        "generation_id": generation_id,
        "committed_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        **digests.as_dict(),
    }
    path = active_path(run_root)
    write_json_durable(path, payload)
    return path


def read_active(run_root: Path) -> dict[str, Any] | None:
    path = active_path(run_root)
    if not path.is_file():
        return None
    import json

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def read_commit(run_root: Path, generation_id: str) -> dict[str, Any] | None:
    path = commit_path(run_root, generation_id)
    if not path.is_file():
        return None
    import json

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def gc_uncommitted_generations(
    run_root: Path,
    *,
    keep_generation_id: str | None = None,
) -> list[str]:
    """Remove generation dirs that lack COMMIT.json."""
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
    """Delete committed gens other than ACTIVE and optional retain set.

    Call only after manifest publication succeeds.
    """
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
