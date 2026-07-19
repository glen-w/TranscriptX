"""Explicit output-manifest entries for active synthesis generation."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from transcriptx.core.analysis.group_llm_synthesis.generation import read_active
from transcriptx.core.analysis.group_llm_synthesis.paths import generation_dir
from transcriptx.core.analysis.group_llm_synthesis.resolve import (
    ResolverCache,
    load_commit_cache,
)


def build_synthesis_manifest_artifacts(
    run_root: Path,
    *,
    inventory_entries: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Build manifest artifact dicts for the ACTIVE generation.

    ``inventory_entries`` may be passed from a just-published attempt
    (rel_path already prefixed with ``.group_llm_synthesis/generations/...``).
    Otherwise load from ACTIVE/COMMIT.
    """
    run_root = Path(run_root)
    artifacts: list[dict[str, Any]] = []
    entries = list(inventory_entries or [])
    if not entries:
        cache = ResolverCache()
        if not load_commit_cache(run_root, cache):
            return []
        assert cache.generation_id is not None
        prefix = f".group_llm_synthesis/generations/{cache.generation_id}/"
        for rel, inv in cache.inventory.items():
            entries.append(
                {
                    "rel_path": prefix + rel,
                    "module": str(inv.get("module") or "llm_summary"),
                    "kind": str(inv.get("kind") or "data_json"),
                }
            )

    for entry in entries:
        rel = entry["rel_path"]
        path = run_root / rel
        if not path.is_file():
            continue
        stats = path.stat()
        module = entry.get("module") or "llm_summary"
        kind = entry.get("kind") or "data_json"
        artifact_id = hashlib.sha256(
            f"{kind}|{module}|global|None|{rel}".encode("utf-8")
        ).hexdigest()[:16]
        artifacts.append(
            {
                "id": artifact_id,
                "kind": kind,
                "module": module,
                "scope": "global",
                "speaker": None,
                "subview": None,
                "slice_id": None,
                "rel_path": rel,
                "bytes": stats.st_size,
                "mtime": datetime.utcfromtimestamp(stats.st_mtime).isoformat() + "Z",
                "mime": (
                    "application/json" if kind == "data_json" else "text/markdown"
                ),
                "tags": ["group_llm_synthesis"],
                "title": Path(rel).name,
                "produced_by": f"{module}/group_llm_synthesis",
                "preview": None,
                "meta": {"group_llm_synthesis": True},
            }
        )
    return artifacts


def merge_synthesis_into_manifest(
    manifest: dict[str, Any],
    run_root: Path,
    *,
    inventory_entries: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Append synthesis artifacts; drop any scanned ``.group_llm_synthesis`` noise."""
    arts = [
        a
        for a in (manifest.get("artifacts") or [])
        if not str(a.get("rel_path") or "").startswith(".group_llm_synthesis/")
    ]
    arts.extend(
        build_synthesis_manifest_artifacts(
            run_root, inventory_entries=inventory_entries
        )
    )
    manifest = dict(manifest)
    manifest["artifacts"] = arts
    # refresh total size
    total = sum(int(a.get("bytes") or 0) for a in arts)
    meta = dict(manifest.get("run_metadata") or {})
    meta["total_size_bytes"] = total
    active = read_active(run_root)
    if active:
        meta["group_llm_synthesis_generation_id"] = active.get("generation_id")
        meta["group_llm_synthesis_overall_status"] = active.get("overall_status")
    manifest["run_metadata"] = meta
    return manifest


def generation_path_for_rel(run_root: Path, generation_rel: str) -> Path:
    """Map COMMIT-relative path to absolute under ACTIVE generation."""
    cache = ResolverCache()
    if not load_commit_cache(run_root, cache) or not cache.generation_id:
        raise FileNotFoundError("no active synthesis generation")
    return generation_dir(run_root, cache.generation_id) / generation_rel
