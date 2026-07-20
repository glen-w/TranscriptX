"""Resolve chart LLM descriptions from ACTIVE generation (fail closed)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from transcriptx.core.analysis.chart_descriptions.inventory import (
    LogicalChartDescriptor,
)
from transcriptx.core.analysis.chart_descriptions.models import ChartDescriptionArtifact
from transcriptx.core.analysis.chart_descriptions.paths import generation_dir
from transcriptx.core.analysis.chart_descriptions.publisher import (
    active_matches_attempt,
    read_active,
)


@dataclass
class DescriptionResolverCache:
    run_root: str = ""
    generation_id: str | None = None
    attempt_epoch: str | None = None
    run_target_id: str | None = None
    run_kind: str | None = None
    by_chart_key: dict[str, str] = field(default_factory=dict)
    loaded: bool = False


_CACHE: DescriptionResolverCache = DescriptionResolverCache()


def cache_identity(run_root: Path) -> tuple[str | None, str | None]:
    active = read_active(run_root)
    if not active or not active_matches_attempt(run_root):
        return None, None
    return (
        str(active.get("generation_id") or "") or None,
        str(active.get("attempt_epoch") or "") or None,
    )


def invalidate_resolver_cache() -> None:
    global _CACHE
    _CACHE = DescriptionResolverCache()


def _read_inventory_identity(
    run_root: Path, generation_id: str
) -> tuple[str | None, str | None]:
    """Return (run_target_id, run_kind) from ACTIVE inventory_snapshot."""
    snap_path = generation_dir(run_root, generation_id) / "inventory_snapshot.json"
    if not snap_path.is_file():
        return None, None
    try:
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    if not isinstance(snap, dict):
        return None, None
    target = snap.get("run_target_id")
    kind = snap.get("run_kind")
    return (
        str(target).strip() if isinstance(target, str) and target.strip() else None,
        str(kind).strip() if isinstance(kind, str) and kind.strip() else None,
    )


def _manifest_transcript_key(run_root: Path) -> str | None:
    path = Path(run_root) / "manifest.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    meta = data.get("run_metadata")
    if not isinstance(meta, dict):
        return None
    key = meta.get("transcript_key")
    return str(key).strip() if isinstance(key, str) and key.strip() else None


def resolve_gallery_run_identity(run_root: Path) -> tuple[str, str | None]:
    """Identity used when building gallery chart_keys.

    Prefer ACTIVE inventory_snapshot (exact generation inputs), then manifest
    ``transcript_key``, then the run folder name. ``run_kind`` is only set when
    known from the snapshot.
    """
    cache = _ensure_cache(Path(run_root))
    if cache.run_target_id:
        return cache.run_target_id, cache.run_kind
    manifest_key = _manifest_transcript_key(run_root)
    if manifest_key:
        return manifest_key, cache.run_kind
    return Path(run_root).name, cache.run_kind


def _ensure_cache(run_root: Path) -> DescriptionResolverCache:
    global _CACHE
    run_root = Path(run_root)
    gen_id, epoch = cache_identity(run_root)
    if (
        _CACHE.loaded
        and _CACHE.run_root == str(run_root)
        and _CACHE.generation_id == gen_id
        and _CACHE.attempt_epoch == epoch
    ):
        return _CACHE
    cache = DescriptionResolverCache(run_root=str(run_root))
    if not gen_id or not epoch:
        _CACHE = cache
        cache.loaded = True
        return cache
    target_id, run_kind = _read_inventory_identity(run_root, gen_id)
    cache.run_target_id = target_id
    cache.run_kind = run_kind
    index_path = generation_dir(run_root, gen_id) / "index.json"
    if not index_path.is_file():
        _CACHE = cache
        cache.loaded = True
        return cache
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        _CACHE = cache
        cache.loaded = True
        return cache
    by_key: dict[str, str] = {}
    for entry in index.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "success":
            continue
        key = entry.get("chart_key")
        rel = entry.get("description_rel")
        if isinstance(key, str) and isinstance(rel, str):
            by_key[key] = rel
    cache.generation_id = gen_id
    cache.attempt_epoch = epoch
    cache.by_chart_key = by_key
    cache.loaded = True
    _CACHE = cache
    return cache


def resolve_chart_llm_description_by_key(
    run_root: Path,
    chart_key: str,
) -> str | None:
    """Fail-closed resolve by exact chart_key. Never falls back to viz_id."""
    if not chart_key:
        return None
    cache = _ensure_cache(run_root)
    if not cache.generation_id:
        return None
    rel = cache.by_chart_key.get(chart_key)
    if not rel:
        return None
    path = generation_dir(run_root, cache.generation_id) / rel
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        artifact = ChartDescriptionArtifact.model_validate(payload)
    except Exception:
        return None
    if artifact.chart_key != chart_key:
        return None
    text = (artifact.description or "").strip()
    return text or None


def resolve_chart_llm_description_for_descriptor(
    run_root: Path,
    chart: LogicalChartDescriptor,
) -> str | None:
    return resolve_chart_llm_description_by_key(run_root, chart.chart_key)


def build_chart_key_for_artifact_fields(
    *,
    run_target_id: str,
    viz_id: str,
    module: str,
    scope: str,
    speaker: str | None,
    slice_id: str | None,
    source_run_id: str | None,
    member_session_id: str | None,
    name: str | None = None,
) -> str:
    from transcriptx.core.analysis.chart_descriptions.chart_key import (
        build_chart_key_payload,
        build_logical_chart_id,
        chart_key_digest,
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
        slice_identity=slice_id,
        source_run_id=source_run_id,
        member_session_id=member_session_id,
    )
    return chart_key_digest(payload)
