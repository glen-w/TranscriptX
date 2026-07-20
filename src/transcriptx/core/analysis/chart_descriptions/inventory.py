"""Neutral logical-chart inventory descriptors (core layer, no web imports)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from transcriptx.core.analysis.chart_descriptions.chart_key import (
    build_chart_key_payload,
    build_logical_chart_id,
    chart_key_digest,
)
from transcriptx.core.analysis.chart_descriptions.schemas import SCHEMA_LOGICAL_INVENTORY

RunKind = Literal["transcript", "group"]
ProvenanceKind = Literal["transcript", "group_aggregate", "member_session"]


@dataclass(frozen=True)
class ChartRepresentation:
    """One on-disk rendering of a logical chart (png/html)."""

    artifact_id: str
    rel_path: str
    kind: str  # chart_static | chart_dynamic
    format: str  # png | html
    storage_root: str | None = None
    content_sha256: str | None = None


@dataclass(frozen=True)
class LogicalChartDescriptor:
    """Authoritative logical chart unit for selection and description."""

    logical_chart_id: str
    chart_key: str
    chart_key_payload: dict[str, Any]
    viz_id: str
    module: str
    scope: str
    speaker: str | None
    slice_id: str | None
    title: str | None
    run_kind: RunKind
    provenance_kind: ProvenanceKind
    source_run_id: str | None
    member_session_id: str | None
    run_target_id: str
    evidence_rel_path: str | None = None
    evidence_sha256: str | None = None
    representations: tuple[ChartRepresentation, ...] = ()
    registry_description: str | None = None
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["representations"] = [asdict(r) for r in self.representations]
        return d


@dataclass
class LogicalChartInventory:
    schema_id: str = SCHEMA_LOGICAL_INVENTORY
    run_root: str = ""
    run_kind: RunKind = "transcript"
    run_target_id: str = ""
    charts: list[LogicalChartDescriptor] = field(default_factory=list)

    def snapshot_sha256(self) -> str:
        payload = {
            "schema_id": self.schema_id,
            "run_root": self.run_root,
            "run_kind": self.run_kind,
            "run_target_id": self.run_target_id,
            "charts": [c.to_dict() for c in sorted(self.charts, key=lambda x: x.chart_key)],
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def make_descriptor_from_fields(
    *,
    viz_id: str,
    module: str,
    scope: str,
    speaker: str | None,
    slice_id: str | None,
    title: str | None,
    run_kind: RunKind,
    provenance_kind: ProvenanceKind,
    run_target_id: str,
    source_run_id: str | None,
    member_session_id: str | None,
    name: str | None = None,
    evidence_rel_path: str | None = None,
    evidence_sha256: str | None = None,
    representations: list[ChartRepresentation] | None = None,
    registry_description: str | None = None,
    tags: list[str] | None = None,
) -> LogicalChartDescriptor:
    speaker_identity = speaker or None
    logical_id = build_logical_chart_id(
        module=module,
        viz_id=viz_id,
        scope=scope,
        speaker_identity=speaker_identity,
        name=name,
    )
    payload = build_chart_key_payload(
        run_target_id=run_target_id,
        logical_chart_id=logical_id,
        viz_id=viz_id,
        scope=scope,
        speaker_identity=speaker_identity,
        slice_identity=slice_id,
        source_run_id=source_run_id,
        member_session_id=member_session_id,
    )
    return LogicalChartDescriptor(
        logical_chart_id=logical_id,
        chart_key=chart_key_digest(payload),
        chart_key_payload=payload,
        viz_id=viz_id,
        module=module,
        scope=scope,
        speaker=speaker,
        slice_id=slice_id,
        title=title,
        run_kind=run_kind,
        provenance_kind=provenance_kind,
        source_run_id=source_run_id,
        member_session_id=member_session_id,
        run_target_id=run_target_id,
        evidence_rel_path=evidence_rel_path,
        evidence_sha256=evidence_sha256,
        representations=tuple(representations or ()),
        registry_description=registry_description,
        tags=tuple(tags or ()),
    )
