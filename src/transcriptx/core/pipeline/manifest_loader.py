"""
Typed manifest loaders. All consumers must load manifest files through these helpers
so the correct manifest type is used; no raw json.load() on manifest files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from transcriptx.core.pipeline.run_schema import (
    MANIFEST_TYPE_ARTIFACT,
    MANIFEST_TYPE_RUN,
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
        # Backward compat: old manifests without manifest_type are artifact manifests
        data = {**data, "manifest_type": MANIFEST_TYPE_ARTIFACT}
    elif manifest_type != MANIFEST_TYPE_ARTIFACT:
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
        # Backward compat: old manifests without manifest_type are run manifests
        data = {**data, "manifest_type": MANIFEST_TYPE_RUN}
    elif manifest_type != MANIFEST_TYPE_RUN:
        raise ValueError(
            f"Expected manifest_type {MANIFEST_TYPE_RUN!r} at {path}, got {manifest_type!r}"
        )
    return data
