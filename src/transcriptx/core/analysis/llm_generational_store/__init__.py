"""Reusable LLM generational store (ACTIVE / COMMIT / generations).

Extracted pattern from group LLM synthesis for enrichment sidecars.
Empty inventory digests are rejected on commit (hardened vs historical
group synthesis debt that allowed ``sha256=""`` for missing files).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from transcriptx.io.atomic_json import write_bytes_atomic, write_json_atomic

SCHEMA_ACTIVE = "llm_generational_active_v1"
SCHEMA_COMMIT = "llm_generational_commit_v1"


def new_generation_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}_{secrets.token_hex(4)}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


@dataclass
class StagedGeneration:
    """One in-progress generation under ``{store_root}/generations/{id}/``."""

    store_root: Path
    generation_id: str
    extra_meta: dict[str, Any] = field(default_factory=dict)

    @property
    def directory(self) -> Path:
        return self.store_root / "generations" / self.generation_id

    def write_json(self, rel_path: str, payload: Any, *, indent: int | None = 2) -> Path:
        dest = self.directory / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(dest, payload, indent=indent)
        return dest

    def write_bytes(self, rel_path: str, data: bytes) -> Path:
        dest = self.directory / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_bytes_atomic(dest, data)
        return dest


def begin_generation(
    module_or_run_root: Path,
    *,
    store_dirname: str,
    extra_meta: Mapping[str, Any] | None = None,
) -> StagedGeneration:
    store_root = Path(module_or_run_root) / store_dirname
    store_root.mkdir(parents=True, exist_ok=True)
    (store_root / "generations").mkdir(parents=True, exist_ok=True)
    gid = new_generation_id()
    staged = StagedGeneration(
        store_root=store_root,
        generation_id=gid,
        extra_meta=dict(extra_meta or {}),
    )
    staged.directory.mkdir(parents=True, exist_ok=True)
    return staged


def build_inventory(
    staged: StagedGeneration,
    rel_paths: list[str],
    *,
    reject_empty: bool = True,
) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for rel in rel_paths:
        path = staged.directory / rel
        if not path.is_file():
            digest = ""
        else:
            digest = sha256_file(path)
        if reject_empty and not digest:
            raise ValueError(
                f"llm_generational_store: empty digest for inventory entry {rel!r}"
            )
        inventory.append({"rel_path": rel, "sha256": digest})
    return inventory


def commit_generation(
    staged: StagedGeneration,
    *,
    inventory: list[dict[str, Any]],
    status: str,
    schema_commit: str = SCHEMA_COMMIT,
) -> Path:
    for entry in inventory:
        if not str(entry.get("sha256") or "").strip():
            raise ValueError(
                "llm_generational_store: COMMIT refused empty inventory digest"
            )
    payload = {
        "schema_version": schema_commit,
        "generation_id": staged.generation_id,
        "committed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "inventory": inventory,
        **staged.extra_meta,
    }
    path = staged.directory / "COMMIT.json"
    write_json_atomic(path, payload, indent=2)
    return path


def activate_generation(
    staged: StagedGeneration,
    *,
    status: str,
    schema_active: str = SCHEMA_ACTIVE,
) -> Path:
    payload = {
        "schema_version": schema_active,
        "generation_id": staged.generation_id,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        **staged.extra_meta,
    }
    path = staged.store_root / "ACTIVE.json"
    write_json_atomic(path, payload, indent=2)
    return path


def commit_and_activate(
    staged: StagedGeneration,
    *,
    rel_paths: list[str],
    status: str,
) -> str:
    inventory = build_inventory(staged, rel_paths, reject_empty=True)
    commit_generation(staged, inventory=inventory, status=status)
    activate_generation(staged, status=status)
    return staged.generation_id


def read_active(store_root: Path) -> dict[str, Any] | None:
    path = Path(store_root) / "ACTIVE.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def read_commit(store_root: Path, generation_id: str) -> dict[str, Any] | None:
    path = Path(store_root) / "generations" / generation_id / "COMMIT.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def load_active_artifact(
    store_root: Path, rel_path: str
) -> Any | None:
    active = read_active(store_root)
    if not active:
        return None
    gid = str(active.get("generation_id") or "")
    if not gid:
        return None
    commit = read_commit(store_root, gid)
    if not commit:
        return None
    path = Path(store_root) / "generations" / gid / rel_path
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def gc_uncommitted(store_root: Path, *, keep_generation_id: str | None = None) -> list[str]:
    removed: list[str] = []
    root = Path(store_root) / "generations"
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
