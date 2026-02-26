"""
Lightweight Pydantic schemas for run-level artifacts (run_results.json, manifest run_metadata).
Used for validation in tests and optional on-write checks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModuleSkippedEntry(BaseModel):
    """One skipped module with reason."""

    module: str
    reason: str


class RunResultsSummary(BaseModel):
    """Schema for run_results.json (run-level results summary)."""

    schema_version: int = Field(..., ge=1)
    run_id: str
    transcript_key: str
    modules_enabled: List[str]
    modules_run: List[str]
    modules_skipped: List[ModuleSkippedEntry]
    modules_failed: List[str]
    errors: List[str]
    preset_explanation: Optional[str] = None

    @classmethod
    def validate_run_results(cls, data: Dict[str, Any]) -> "RunResultsSummary":
        """Validate a run_results payload (e.g. from run_results.json)."""
        # Normalize modules_skipped to list of dicts for Pydantic
        skipped = data.get("modules_skipped") or []
        normalized = [
            (
                {"module": s["module"], "reason": s.get("reason", "Skipped")}
                if isinstance(s, dict)
                else {"module": str(s), "reason": "Not in registry"}
            )
            for s in skipped
        ]
        data = {**data, "modules_skipped": normalized}
        return cls.model_validate(data)


class ManifestRunMetadata(BaseModel):
    """Schema for manifest.json run_metadata section."""

    timestamp: str
    transcript_key: str
    modules_enabled: List[str]
    total_size_bytes: int
    version_hash: Optional[Dict[str, Optional[str]]] = None
    audio_rel_path: Optional[str] = None


class ManifestArtifactEntry(BaseModel):
    """Minimal schema for one artifact in manifest.json artifacts list."""

    id: str
    kind: str
    rel_path: str
    bytes: int
    mtime: str
    mime: str
    tags: List[str]
    module: Optional[str] = None
    scope: Optional[str] = None
    speaker: Optional[str] = None


def validate_manifest_shape(manifest: Dict[str, Any]) -> None:
    """Validate manifest.json has required top-level shape and run_metadata."""
    assert "run_id" in manifest
    assert "run_metadata" in manifest
    assert "artifacts" in manifest
    ManifestRunMetadata.model_validate(manifest["run_metadata"])
    for a in manifest["artifacts"]:
        ManifestArtifactEntry.model_validate(a)
