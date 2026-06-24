"""Block rendering context — no raw session_state in blocks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcriptx.web.blocks.loader import ArtifactContentLoader
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services import ArtifactService


@dataclass(frozen=True)
class BlockServices:
    """Facades to existing services (reuse-first; no duplicate implementations)."""

    artifact_service: type[ArtifactService] = ArtifactService
    content_loader: ArtifactContentLoader | None = None


@dataclass(frozen=True)
class BlockContext:
    run_root: Path | None
    subject_type: str | None
    subject_id: str | None
    run_id: str | None
    session_name: str | None
    artifacts: tuple[Artifact, ...]
    run_results: dict[str, Any] | None
    services: BlockServices
    layout_profile_id: str
    health: dict[str, Any] | None = None


def build_block_context(
    *,
    run_root: Path | None,
    subject_type: str | None,
    subject_id: str | None,
    run_id: str | None,
    session_name: str | None,
    artifacts: list[Artifact] | tuple[Artifact, ...],
    run_results: dict[str, Any] | None,
    layout_profile_id: str,
    health: dict[str, Any] | None = None,
) -> BlockContext:
    loader = (
        ArtifactContentLoader(run_root, tuple(artifacts))
        if run_root is not None
        else None
    )
    return BlockContext(
        run_root=run_root,
        subject_type=subject_type,
        subject_id=subject_id,
        run_id=run_id,
        session_name=session_name,
        artifacts=tuple(artifacts),
        run_results=run_results,
        services=BlockServices(content_loader=loader),
        layout_profile_id=layout_profile_id,
        health=health,
    )
