"""Explicit output-manifest entries for active chart-descriptions generation."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from transcriptx.core.analysis.chart_descriptions.publisher import (
    active_matches_attempt,
    read_active,
)
from transcriptx.core.analysis.chart_descriptions.paths import generation_dir
from transcriptx.core.analysis.chart_descriptions.schemas import MODULE_ID


def build_chart_description_manifest_artifacts(
    run_root: Path,
    *,
    inventory_entries: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    run_root = Path(run_root)
    artifacts: list[dict[str, Any]] = []
    entries = list(inventory_entries or [])
    if not entries:
        if not active_matches_attempt(run_root):
            return []
        active = read_active(run_root)
        if not active:
            return []
        gen_id = str(active.get("generation_id") or "")
        if not gen_id:
            return []
        # Prefer COMMIT inventory if present
        commit_path = generation_dir(run_root, gen_id) / "COMMIT.json"
        if commit_path.is_file():
            import json

            try:
                commit = json.loads(commit_path.read_text(encoding="utf-8"))
            except Exception:
                commit = {}
            prefix = f".chart_descriptions/generations/{gen_id}/"
            for inv in commit.get("artifacts") or []:
                if isinstance(inv, dict) and inv.get("rel_path"):
                    entries.append(
                        {
                            "rel_path": prefix + str(inv["rel_path"]),
                            "module": str(inv.get("module") or MODULE_ID),
                            "kind": str(inv.get("kind") or "data_json"),
                        }
                    )

    for entry in entries:
        rel = entry["rel_path"]
        path = run_root / rel
        if not path.is_file():
            continue
        stats = path.stat()
        module = entry.get("module") or MODULE_ID
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
                "tags": ["chart_descriptions"],
                "title": Path(rel).name,
                "produced_by": f"{module}/chart_descriptions",
                "preview": None,
                "meta": {"chart_descriptions": True},
            }
        )
    return artifacts


def merge_chart_descriptions_into_manifest(
    manifest: dict[str, Any],
    run_root: Path,
    *,
    inventory_entries: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    arts = [
        a
        for a in (manifest.get("artifacts") or [])
        if not str(a.get("rel_path") or "").startswith(".chart_descriptions/")
    ]
    arts.extend(
        build_chart_description_manifest_artifacts(
            run_root, inventory_entries=inventory_entries
        )
    )
    manifest = dict(manifest)
    manifest["artifacts"] = arts
    total = sum(int(a.get("bytes") or 0) for a in arts)
    meta = dict(manifest.get("run_metadata") or {})
    meta["total_size_bytes"] = total
    if active_matches_attempt(run_root):
        active = read_active(run_root)
        if active:
            meta["chart_descriptions_generation_id"] = active.get("generation_id")
            meta["chart_descriptions_attempt_epoch"] = active.get("attempt_epoch")
            meta["chart_descriptions_overall_status"] = active.get("overall_status")
    manifest["run_metadata"] = meta
    return manifest
