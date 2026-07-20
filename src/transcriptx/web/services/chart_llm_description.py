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
    resolve_gallery_run_identity,
)
from transcriptx.web.models.artifact import Artifact


def _member_session_id(artifact: Artifact) -> str | None:
    if artifact.storage_root:
        return Path(artifact.storage_root).name
    if artifact.has_tag("member_session"):
        return artifact.slice_id
    return None


def _source_run_id(
    artifact: Artifact,
    *,
    run_target_id: str,
    run_kind: str | None,
) -> str | None:
    """Match inventory_builder provenance for chart_key digests.

    Transcript root charts stamp ``source_run_id=run_target_id``. Group aggregate
    charts leave it empty. Member charts use the member run folder name.
    """
    if artifact.storage_root:
        return Path(artifact.storage_root).name
    if run_kind == "transcript":
        return run_target_id
    if run_kind == "group":
        return None
    # Unknown kind (e.g. snapshot missing): infer from transcript-hash targets.
    if str(run_target_id).startswith("sha256:"):
        return run_target_id
    return None


def chart_key_for_gallery_artifact(
    artifact: Artifact,
    *,
    run_target_id: str,
    run_kind: str | None = None,
) -> str | None:
    meta = artifact.meta or {}
    viz_id = meta.get("viz_id")
    if not isinstance(viz_id, str) or not viz_id.strip():
        return None
    # Prefer meta.* to match inventory_builder (manifest module id can differ from
    # gallery folder label, e.g. voice_charts_core vs voice).
    module = str(meta.get("module") or artifact.module or "")
    scope = str(meta.get("scope") or artifact.scope or "global")
    if meta.get("speaker") is not None:
        speaker = str(meta.get("speaker"))
    else:
        speaker = artifact.speaker
    name = str(meta.get("name") or "") or None
    member_id = _member_session_id(artifact)
    source_run = _source_run_id(
        artifact, run_target_id=run_target_id, run_kind=run_kind
    )
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
    run_kind: str | None = None,
) -> str | None:
    """Resolve LLM narrative for a gallery artifact via exact chart_key."""
    if run_target_id is None or run_kind is None:
        target, kind = resolve_gallery_run_identity(run_root)
        if run_target_id is None:
            run_target_id = target
        if run_kind is None:
            run_kind = kind
    key = chart_key_for_gallery_artifact(
        artifact, run_target_id=run_target_id, run_kind=run_kind
    )
    if not key:
        return None
    return resolve_chart_llm_description_by_key(run_root, key)
