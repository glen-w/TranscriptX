"""
Typed manifest loaders. All consumers must load manifest files through these helpers
so the correct manifest type is used; no raw json.load() on manifest files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.pipeline.run_schema import (
    MANIFEST_TYPE_ARTIFACT,
    MANIFEST_TYPE_RUN,
    RunResultsSummary,
)
from transcriptx.core.pipeline.module_outcomes import (
    assert_run_results_schema_supported,
)


def load_artifact_manifest(path: str | Path) -> Dict[str, Any]:
    """
    Load the artifact manifest (run root manifest.json).
    Validates manifest_type is "artifact_manifest"; raises if wrong type or missing.
    """
    path = Path(path)
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Artifact manifest at {path} is not a JSON object")
    manifest_type = data.get("manifest_type")
    if manifest_type is None:
        raise ValueError(
            f"Artifact manifest at {path} missing required manifest_type {MANIFEST_TYPE_ARTIFACT!r}"
        )
    if manifest_type != MANIFEST_TYPE_ARTIFACT:
        raise ValueError(
            f"Expected manifest_type {MANIFEST_TYPE_ARTIFACT!r} at {path}, got {manifest_type!r}"
        )
    return data


def load_run_manifest(path: str | Path) -> Dict[str, Any]:
    """
    Load the run manifest (.transcriptx/manifest.json).
    Validates manifest_type is "run_manifest"; raises if wrong type or missing.
    """
    path = Path(path)
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Run manifest at {path} is not a JSON object")
    manifest_type = data.get("manifest_type")
    if manifest_type is None:
        raise ValueError(
            f"Run manifest at {path} missing required manifest_type {MANIFEST_TYPE_RUN!r}"
        )
    if manifest_type != MANIFEST_TYPE_RUN:
        raise ValueError(
            f"Expected manifest_type {MANIFEST_TYPE_RUN!r} at {path}, got {manifest_type!r}"
        )
    return data


def load_run_results(path: str | Path) -> Dict[str, Any]:
    """
    Load and validate run_results.json.
    Normalizes skipped rows using RunResultsSummary schema validation.
    """
    path = Path(path)
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"run_results at {path} is not a JSON object")
    assert_run_results_schema_supported(data)

    rid = data.get("run_id")
    if rid is None or (isinstance(rid, str) and not rid.strip()):
        raise ValueError(
            f"run_results at {path} missing or empty required field 'run_id'"
        )
    tkey = data.get("transcript_key")
    if tkey is None or (isinstance(tkey, str) and not str(tkey).strip()):
        raise ValueError(
            f"run_results at {path} missing or empty required field 'transcript_key'"
        )

    list_fields = (
        "modules_enabled",
        "modules_run",
        "modules_skipped",
        "modules_failed",
        "errors",
    )
    for name in list_fields:
        val = data.get(name)
        if val is None:
            raise ValueError(
                f"run_results at {path} has null for required list field {name!r}"
            )

    normalized = {
        "schema_version": data.get("schema_version"),
        "run_id": rid,
        "transcript_key": tkey,
        "modules_enabled": data.get("modules_enabled"),
        "modules_run": data.get("modules_run"),
        "modules_skipped": data.get("modules_skipped"),
        "modules_failed": data.get("modules_failed"),
        "errors": data.get("errors"),
        "preset_explanation": data.get("preset_explanation"),
        "analysis_preset": data.get("analysis_preset"),
        "module_outcomes": data.get("module_outcomes"),
    }
    return RunResultsSummary.validate_run_results(normalized).model_dump()


@dataclass(frozen=True)
class RunOutcomeContext:
    """Typed loader bundle for canonical read-side projection."""

    run_results: Dict[str, Any]
    artifact_manifest: Optional[Dict[str, Any]] = None


def load_run_outcome_context(run_dir: str | Path) -> RunOutcomeContext:
    """
    Load run_results and optional artifact manifest for a run directory.
    run_results is required on canonical truth path; manifest is best-effort.
    """
    run_dir = Path(run_dir)
    run_results = load_run_results(run_dir / "run_results.json")
    manifest: Optional[Dict[str, Any]] = None
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = load_artifact_manifest(manifest_path)
        except Exception:
            manifest = None
    return RunOutcomeContext(run_results=run_results, artifact_manifest=manifest)


def load_group_member_runs(path: str | Path) -> List[Dict[str, Any]]:
    """Load group_member_runs.json members list; returns [] when missing/invalid."""
    path = Path(path)
    if not path.exists():
        return []
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return []
    members = data.get("members")
    if not isinstance(members, list):
        return []
    return [m for m in members if isinstance(m, dict)]


def load_group_phase_metadata(run_dir: str | Path) -> List[Dict[str, Any]]:
    """
    Load group-phase outcome metadata for a group run directory.

    Today this data is persisted in aggregation_warnings.json. We expose a neutral
    loader name so call sites do not encode filename semantics.
    """
    path = Path(run_dir) / "aggregation_warnings.json"
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]
