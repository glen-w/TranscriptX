"""Normalised plotted chart evidence (primary grounding for LLM descriptions)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from transcriptx.core.analysis.chart_descriptions.schemas import (
    MAX_EVIDENCE_BYTES,
    MAX_EVIDENCE_LABELS,
    MAX_EVIDENCE_VALUES,
    SCHEMA_EVIDENCE,
)
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    BoxSpec,
    ChartSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
    NetworkGraphSpec,
    ScatterSpec,
)


@dataclass
class ChartEvidence:
    """Exact plotted evidence for one logical chart unit."""

    schema_id: str = SCHEMA_EVIDENCE
    viz_id: str = ""
    module: str = ""
    scope: str = "global"
    speaker: str | None = None
    chart_intent: str | None = None
    title: str | None = None
    x_label: str | None = None
    y_label: str | None = None
    labels: list[str] = field(default_factory=list)
    values: list[Any] = field(default_factory=list)
    units: dict[str, str] = field(default_factory=dict)
    filters: dict[str, Any] = field(default_factory=dict)
    denominator: str | None = None
    transformations: list[str] = field(default_factory=list)
    series: list[dict[str, Any]] = field(default_factory=list)
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def content_sha256(self) -> str:
        payload = {k: v for k, v in self.to_dict().items() if k != "schema_id"}
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _truncate_seq(values: Sequence[Any], limit: int) -> list[Any]:
    out = list(values)[:limit]
    return out


def evidence_from_chart_spec(spec: ChartSpec) -> ChartEvidence:
    """Extract plotted evidence from a ChartSpec (primary path)."""
    labels: list[str] = []
    values: list[Any] = []
    series: list[dict[str, Any]] = []
    transformations: list[str] = []

    if isinstance(spec, BarCategoricalSpec):
        labels = [str(x) for x in _truncate_seq(spec.categories, MAX_EVIDENCE_LABELS)]
        values = list(_truncate_seq(spec.values, MAX_EVIDENCE_VALUES))
        if spec.series:
            for item in list(spec.series)[:16]:
                if isinstance(item, Mapping):
                    series.append(dict(item))
        transformations.append(f"orientation:{spec.orientation}")
    elif isinstance(spec, LineTimeSeriesSpec):
        for item in list(spec.series)[:16]:
            if isinstance(item, Mapping):
                series.append(
                    {
                        "name": item.get("name"),
                        "x": _truncate_seq(item.get("x") or [], 64),
                        "y": _truncate_seq(item.get("y") or [], 64),
                    }
                )
        transformations.append(f"x_type:{spec.x_type}")
        transformations.append(f"y_type:{spec.y_type}")
    elif isinstance(spec, HeatmapMatrixSpec):
        labels = [str(x) for x in _truncate_seq(spec.x_labels, MAX_EVIDENCE_LABELS)]
        series.append(
            {
                "y_labels": [
                    str(y) for y in _truncate_seq(spec.y_labels, MAX_EVIDENCE_LABELS)
                ],
                "z_rows": len(spec.z),
                "z_sample": [list(_truncate_seq(row, 16)) for row in list(spec.z)[:8]],
            }
        )
    elif isinstance(spec, BoxSpec):
        for item in list(spec.series)[:16]:
            if isinstance(item, Mapping):
                series.append(dict(item))
    elif isinstance(spec, NetworkGraphSpec):
        series.append(
            {
                "nodes": [
                    {"id": n.get("id"), "label": n.get("label")}
                    for n in list(spec.nodes)[:32]
                    if isinstance(n, Mapping)
                ],
                "edge_count": len(spec.edges),
            }
        )
    elif isinstance(spec, ScatterSpec):
        for s in spec.get_series()[:8]:
            series.append(
                {
                    "name": s.name,
                    "x": _truncate_seq(s.x, 64),
                    "y": _truncate_seq(s.y, 64),
                }
            )

    return ChartEvidence(
        viz_id=spec.viz_id,
        module=spec.module,
        scope=spec.scope,
        speaker=spec.speaker,
        chart_intent=spec.chart_intent,
        title=spec.title,
        x_label=spec.x_label,
        y_label=spec.y_label,
        labels=labels,
        values=values,
        series=series,
        transformations=transformations,
        notes=spec.notes,
    )


def evidence_within_caps(evidence: ChartEvidence) -> bool:
    blob = json.dumps(evidence.to_dict(), sort_keys=True, default=str).encode("utf-8")
    return len(blob) <= MAX_EVIDENCE_BYTES


def parse_evidence_payload(payload: Mapping[str, Any]) -> ChartEvidence | None:
    if not isinstance(payload, Mapping):
        return None
    if payload.get("schema_id") not in {SCHEMA_EVIDENCE, None}:
        # Accept missing schema_id only for legacy fallback callers that set it later.
        if payload.get("schema_id") and payload.get("schema_id") != SCHEMA_EVIDENCE:
            return None
    try:
        return ChartEvidence(
            schema_id=str(payload.get("schema_id") or SCHEMA_EVIDENCE),
            viz_id=str(payload.get("viz_id") or ""),
            module=str(payload.get("module") or ""),
            scope=str(payload.get("scope") or "global"),
            speaker=payload.get("speaker"),
            chart_intent=payload.get("chart_intent"),
            title=payload.get("title"),
            x_label=payload.get("x_label"),
            y_label=payload.get("y_label"),
            labels=[
                str(x) for x in list(payload.get("labels") or [])[:MAX_EVIDENCE_LABELS]
            ],
            values=list(payload.get("values") or [])[:MAX_EVIDENCE_VALUES],
            units=dict(payload.get("units") or {}),
            filters=dict(payload.get("filters") or {}),
            denominator=payload.get("denominator"),
            transformations=[
                str(t) for t in list(payload.get("transformations") or [])
            ],
            series=[
                dict(s)
                for s in list(payload.get("series") or [])
                if isinstance(s, Mapping)
            ],
            notes=payload.get("notes"),
        )
    except Exception:
        return None
