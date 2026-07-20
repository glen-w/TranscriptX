"""Build logical chart inventory from authoritative run artifacts_meta + files."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

from transcriptx.core.analysis.chart_descriptions.digests import sha256_file
from transcriptx.core.analysis.chart_descriptions.inventory import (
    ChartRepresentation,
    LogicalChartDescriptor,
    LogicalChartInventory,
    ProvenanceKind,
    RunKind,
    make_descriptor_from_fields,
)
from transcriptx.core.analysis.chart_descriptions.path_safety import (
    assert_path_within_roots,
    is_path_within_roots,
)
from transcriptx.core.utils.chart_registry import find_chart_definition_for_artifact
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def _load_artifacts_meta(run_root: Path) -> dict[str, Any]:
    path = Path(run_root) / ".transcriptx" / "artifacts_meta.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _artifact_id(kind: str, module: str, scope: str, speaker: str | None, rel: str) -> str:
    return hashlib.sha256(
        f"{kind}|{module}|{scope}|{speaker}|{rel}".encode("utf-8")
    ).hexdigest()[:16]


def _infer_kind(rel_path: str, meta: dict[str, Any]) -> str:
    hint = str(meta.get("render_hint") or "")
    fmt = str(meta.get("format") or "")
    lower = rel_path.lower()
    if hint == "dynamic" or fmt == "html" or lower.endswith(".html"):
        return "chart_dynamic"
    return "chart_static"


def _provenance(
    *,
    run_kind: RunKind,
    storage_root: str | None,
    tags: list[str],
) -> ProvenanceKind:
    if storage_root or "member_session" in tags:
        return "member_session"
    if run_kind == "group" or "group_aggregate" in tags:
        return "group_aggregate"
    return "transcript"


def build_logical_chart_inventory(
    run_root: Path,
    *,
    run_kind: RunKind,
    run_target_id: str,
    allowed_roots: list[Path] | None = None,
    member_charts: list[dict[str, Any]] | None = None,
) -> tuple[LogicalChartInventory, list[dict[str, Any]]]:
    """Snapshot logical charts from artifacts_meta (+ optional member embeds).

    Returns (inventory, skip_records).
    """
    run_root = Path(run_root)
    roots = list(allowed_roots or [run_root])
    skips: list[dict[str, Any]] = []
    meta_map = _load_artifacts_meta(run_root)

    # Group representations by logical grouping key before chart_key.
    buckets: dict[tuple[Any, ...], list[tuple[str, dict[str, Any], Path | None]]] = defaultdict(
        list
    )

    def _consider(
        rel_path: str,
        meta: dict[str, Any],
        *,
        storage_root: str | None = None,
        source_run_id: str | None = None,
        member_session_id: str | None = None,
        extra_tags: list[str] | None = None,
    ) -> None:
        if not isinstance(meta, dict):
            skips.append({"rel_path": rel_path, "reason": "malformed_meta"})
            return
        if meta.get("artifact_kind") not in {None, "chart"} and "charts/" not in rel_path:
            return
        if "charts/" not in rel_path.replace("\\", "/"):
            # Only chart paths
            if meta.get("artifact_kind") != "chart":
                return
        viz_id = meta.get("viz_id")
        if not isinstance(viz_id, str) or not viz_id.strip():
            skips.append({"rel_path": rel_path, "reason": "missing_viz_id"})
            return
        base = Path(storage_root) if storage_root else run_root
        abs_path = base / rel_path
        if not is_path_within_roots(abs_path, roots + ([base] if storage_root else [])):
            skips.append({"rel_path": rel_path, "reason": "path_outside_roots"})
            return
        try:
            assert_path_within_roots(abs_path, roots + ([base] if storage_root else []))
        except ValueError:
            skips.append({"rel_path": rel_path, "reason": "path_outside_roots"})
            return
        tags = list(meta.get("tags") or []) + list(extra_tags or [])
        if storage_root and "member_session" not in tags:
            tags.append("member_session")
        scope = str(meta.get("scope") or "global")
        speaker = meta.get("speaker")
        speaker_s = str(speaker) if speaker else None
        module = str(meta.get("module") or "unknown")
        name = meta.get("name")
        bucket_key = (
            viz_id,
            module,
            scope,
            speaker_s or "",
            storage_root or "",
            source_run_id or "",
            member_session_id or "",
            str(name or ""),
        )
        buckets[bucket_key].append((rel_path, meta, abs_path if abs_path.is_file() else None))

    for rel, meta in meta_map.items():
        if not isinstance(meta, dict):
            continue
        tags = list(meta.get("tags") or [])
        _consider(
            str(rel),
            meta,
            storage_root=None,
            source_run_id=run_target_id if run_kind == "transcript" else None,
            member_session_id=None,
            extra_tags=tags,
        )

    for entry in member_charts or []:
        if not isinstance(entry, dict):
            continue
        _consider(
            str(entry.get("rel_path") or ""),
            dict(entry.get("meta") or {}),
            storage_root=entry.get("storage_root"),
            source_run_id=entry.get("source_run_id"),
            member_session_id=entry.get("member_session_id"),
            extra_tags=list(entry.get("tags") or []),
        )

    charts: list[LogicalChartDescriptor] = []
    for bucket_key, items in buckets.items():
        viz_id, module, scope, speaker_s, storage_root, source_run_id, member_id, name = (
            bucket_key
        )
        representations: list[ChartRepresentation] = []
        title = None
        evidence_rel = None
        evidence_sha = None
        tags_acc: set[str] = set()
        for rel_path, meta, abs_path in items:
            kind = _infer_kind(rel_path, meta)
            fmt = "html" if kind == "chart_dynamic" else "png"
            content_hash = None
            if abs_path and abs_path.is_file():
                try:
                    content_hash = sha256_file(abs_path)
                except OSError:
                    content_hash = None
            representations.append(
                ChartRepresentation(
                    artifact_id=_artifact_id(
                        kind, module, scope, speaker_s or None, rel_path
                    ),
                    rel_path=rel_path,
                    kind=kind,
                    format=fmt,
                    storage_root=storage_root or None,
                    content_sha256=content_hash,
                )
            )
            title = title or meta.get("title")
            tags_acc.update(str(t) for t in (meta.get("tags") or []))
            ev = meta.get("evidence_rel") or meta.get("chart_evidence_rel")
            if isinstance(ev, str) and ev:
                evidence_rel = ev
            ev_hash = meta.get("evidence_sha256")
            if isinstance(ev_hash, str) and ev_hash:
                evidence_sha = ev_hash

        # Prefer evidence sidecar next to first representation if meta missing
        if not evidence_rel and representations:
            candidate = (
                Path(representations[0].rel_path).with_suffix("").as_posix()
                + ".evidence.json"
            )
            # Convention: module/.../charts/.../name.evidence.json sibling pattern
            # Also check explicit evidence under data/
            for rep in representations:
                stem = Path(rep.rel_path).name
                parent = str(Path(rep.rel_path).parent)
                for guess in (
                    f"{parent}/{Path(stem).stem}.evidence.json",
                    f"{module}/data/global/{viz_id}.evidence.json",
                ):
                    base = Path(storage_root) if storage_root else run_root
                    if (base / guess).is_file():
                        evidence_rel = guess
                        try:
                            evidence_sha = sha256_file(base / guess)
                        except OSError:
                            pass
                        break
                if evidence_rel:
                    break

        provenance = _provenance(
            run_kind=run_kind,
            storage_root=storage_root or None,
            tags=list(tags_acc),
        )
        registry_description = None
        try:
            # Minimal artifact-like object for registry match
            class _A:
                def __init__(self) -> None:
                    self.meta = {"viz_id": viz_id}
                    self.module = module
                    self.rel_path = representations[0].rel_path if representations else ""
                    self.kind = representations[0].kind if representations else "chart_static"
                    self.tags = list(tags_acc)

            cd = find_chart_definition_for_artifact(_A())
            if cd and cd.description:
                registry_description = cd.description.strip()
        except Exception:
            registry_description = None

        charts.append(
            make_descriptor_from_fields(
                viz_id=viz_id,
                module=module,
                scope=scope,
                speaker=speaker_s or None,
                slice_id=None,
                title=str(title) if title else None,
                run_kind=run_kind,
                provenance_kind=provenance,
                run_target_id=run_target_id,
                source_run_id=source_run_id or None,
                member_session_id=member_id or None,
                name=name or None,
                evidence_rel_path=evidence_rel,
                evidence_sha256=evidence_sha,
                representations=representations,
                registry_description=registry_description,
                tags=sorted(tags_acc),
            )
        )

    # Deduplicate exact chart_keys
    by_key: dict[str, LogicalChartDescriptor] = {}
    for chart in charts:
        existing = by_key.get(chart.chart_key)
        if existing is None:
            by_key[chart.chart_key] = chart
            continue
        merged_reps = list(existing.representations) + [
            r
            for r in chart.representations
            if r.rel_path not in {x.rel_path for x in existing.representations}
        ]
        by_key[chart.chart_key] = replace(
            existing,
            title=existing.title or chart.title,
            evidence_rel_path=existing.evidence_rel_path or chart.evidence_rel_path,
            evidence_sha256=existing.evidence_sha256 or chart.evidence_sha256,
            representations=tuple(merged_reps),
            registry_description=existing.registry_description
            or chart.registry_description,
            tags=tuple(sorted(set(existing.tags) | set(chart.tags))),
        )

    inventory = LogicalChartInventory(
        run_root=str(run_root),
        run_kind=run_kind,
        run_target_id=run_target_id,
        charts=sorted(by_key.values(), key=lambda c: c.chart_key),
    )
    return inventory, skips
