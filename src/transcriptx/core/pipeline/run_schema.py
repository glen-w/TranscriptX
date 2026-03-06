"""
Lightweight Pydantic schemas for run-level artifacts (run_results.json, manifest run_metadata),
and for run input (RunManifestInput) as the canonical pipeline entry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunManifestInput(BaseModel):
    """
    Canonical input for the analysis pipeline. All run paths (CLI flags, --manifest file)
    normalize to this struct before calling run_analysis_pipeline().
    """

    schema_version: int = Field(1, ge=1)
    transcript_path: str = Field(
        ...,
        description="Absolute path to transcript JSON (or directory/glob for batch)",
    )
    modules: List[str] = Field(
        ..., description="Module names to run; use ['all'] for all enabled"
    )
    mode: str = Field("quick", description="Analysis mode: quick or full")
    profile: Optional[str] = Field(None, description="Semantic profile for full mode")
    config_overrides: Optional[Dict[str, Any]] = Field(default_factory=dict)
    output_dir: Optional[str] = None
    include_unidentified_speakers: bool = False
    skip_speaker_gate: bool = False
    skip_confirm: bool = False
    persist: bool = False
    run_id: Optional[str] = Field(
        None, description="If set, use as run_id; else auto-generate"
    )

    @classmethod
    def from_file(cls, path: str | Path) -> "RunManifestInput":
        """Load RunManifestInput from a JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        data = json.loads(path.read_text(encoding="utf-8"))
        if (
            isinstance(data, dict)
            and "config_overrides" in data
            and data["config_overrides"] is None
        ):
            data = {**data, "config_overrides": {}}
        return cls.model_validate(data)

    @classmethod
    def from_cli_kwargs(
        cls,
        transcript_file: str | Path,
        mode: str = "quick",
        modules: Optional[List[str]] = None,
        profile: Optional[str] = None,
        skip_confirm: bool = False,
        output_dir: Optional[str] = None,
        include_unidentified_speakers: bool = False,
        skip_speaker_gate: bool = False,
        persist: bool = False,
        run_id: Optional[str] = None,
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> "RunManifestInput":
        """Build RunManifestInput from CLI-style keyword arguments."""
        transcript_path = str(Path(transcript_file).resolve())
        return cls(
            schema_version=1,
            transcript_path=transcript_path,
            modules=modules or ["all"],
            mode=mode,
            profile=profile,
            config_overrides=config_overrides or {},
            output_dir=output_dir,
            include_unidentified_speakers=include_unidentified_speakers,
            skip_speaker_gate=skip_speaker_gate,
            skip_confirm=skip_confirm,
            persist=persist,
            run_id=run_id,
        )


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


MANIFEST_TYPE_ARTIFACT = "artifact_manifest"
MANIFEST_TYPE_RUN = "run_manifest"


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
    """Validate manifest.json has required top-level shape and run_metadata.
    If manifest_type is present it must be artifact_manifest."""
    if (
        "manifest_type" in manifest
        and manifest["manifest_type"] != MANIFEST_TYPE_ARTIFACT
    ):
        raise ValueError(
            f"Expected manifest_type {MANIFEST_TYPE_ARTIFACT!r}, got {manifest.get('manifest_type')!r}"
        )
    assert "run_id" in manifest
    assert "run_metadata" in manifest
    assert "artifacts" in manifest
    ManifestRunMetadata.model_validate(manifest["run_metadata"])
    for a in manifest["artifacts"]:
        ManifestArtifactEntry.model_validate(a)
