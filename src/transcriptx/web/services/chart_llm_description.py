"""Web helpers: resolve LLM chart descriptions for gallery artifacts."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.analysis.chart_descriptions.chart_key import (
    build_chart_key_payload,
    build_logical_chart_id,
    chart_key_digest,
)
from transcriptx.core.analysis.chart_descriptions.resolve import (
    resolve_chart_llm_description_by_key,
)
from transcriptx.web.models.artifact import Artifact


def _member_session_id(artifact: Artifact) -> str | None:
    if artifact.storage_root:
        return Path(artifact.storage_root).name
    if artifact.has_tag("member_session"):
        return artifact.slice_id
    return None


def chart_key_for_gallery_artifact(
    artifact: Artifact,
    *,
    run_target_id: str,
) -> str | None:
    meta = artifact.meta or {}
    viz_id = meta.get("viz_id")
    if not isinstance(viz_id, str) or not viz_id.strip():
        return None
    module = artifact.module or str(meta.get("module") or "")
    scope = artifact.scope or str(meta.get("scope") or "global")
    speaker = artifact.speaker or (
        str(meta["speaker"]) if meta.get("speaker") else None
    )
    name = str(meta.get("name") or "") or None
    member_id = _member_session_id(artifact)
    source_run = None
    if artifact.storage_root:
        source_run = Path(artifact.storage_root).name
    logical_id = build_logical_chart_id(
        module=module,
        viz_id=viz_id,
        scope=scope,
        speaker_identity=speaker,
        name=name,
    )
    payload = build_chart_key_payload(
        run_target_id=run_target_id,
        logical_chart_id=logical_id,
        viz_id=viz_id,
        scope=scope,
        speaker_identity=speaker,
        slice_identity=artifact.slice_id,
        source_run_id=source_run,
        member_session_id=member_id,
    )
    return chart_key_digest(payload)


def resolve_chart_llm_description(
    run_root: Path,
    artifact: Artifact,
    *,
    run_target_id: str | None = None,
) -> str | None:
    """Resolve LLM narrative for a gallery artifact via exact chart_key."""
    target = run_target_id or Path(run_root).name
    key = chart_key_for_gallery_artifact(artifact, run_target_id=target)
    if not key:
        return None
    return resolve_chart_llm_description_by_key(run_root, key)
