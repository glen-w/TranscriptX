"""
Class-first minimal artifact contracts for reporting (expects_artifacts, etc.).

Per plan: coarse defaults by module category; extend with per-module overrides only
when proven necessary. Registry stays small — this is not a parallel metadata framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from transcriptx.core.pipeline.module_registry import get_module_info

ExpectsArtifacts = Literal["yes", "no", "conditional"]
ArtifactMode = Literal["files", "report_only", "mixed"]
MissingArtifactsAffects = Literal["warn", "error", "ignore"]


@dataclass(frozen=True)
class ModuleArtifactContract:
    expects_artifacts: ExpectsArtifacts
    artifact_mode: ArtifactMode
    missing_artifacts_affects_status: MissingArtifactsAffects


# Defaults by analysis module category (light / medium / heavy).
_CATEGORY_DEFAULTS: dict[str, ModuleArtifactContract] = {
    "light": ModuleArtifactContract(
        expects_artifacts="yes",
        artifact_mode="files",
        missing_artifacts_affects_status="warn",
    ),
    "medium": ModuleArtifactContract(
        expects_artifacts="yes",
        artifact_mode="files",
        missing_artifacts_affects_status="warn",
    ),
    "heavy": ModuleArtifactContract(
        expects_artifacts="yes",
        artifact_mode="mixed",
        missing_artifacts_affects_status="warn",
    ),
}

# Post-processing-only modules often emit no standard tree layout.
_OVERRIDES: dict[str, ModuleArtifactContract] = {
    "corrections": ModuleArtifactContract(
        expects_artifacts="conditional",
        artifact_mode="report_only",
        missing_artifacts_affects_status="ignore",
    ),
}


def get_artifact_contract(module_id: str) -> ModuleArtifactContract:
    """Return contract for a module (class-first + small override table)."""
    if module_id in _OVERRIDES:
        return _OVERRIDES[module_id]
    info = get_module_info(module_id)
    category = (info.category if info else None) or "medium"
    return _CATEGORY_DEFAULTS.get(
        category,
        ModuleArtifactContract(
            expects_artifacts="yes",
            artifact_mode="files",
            missing_artifacts_affects_status="warn",
        ),
    )
