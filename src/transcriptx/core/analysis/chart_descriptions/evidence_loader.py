"""Load and validate evidence for a logical chart."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.analysis.chart_descriptions.evidence import (
    ChartEvidence,
    evidence_within_caps,
    parse_evidence_payload,
)
from transcriptx.core.analysis.chart_descriptions.inventory import (
    LogicalChartDescriptor,
)
from transcriptx.core.analysis.chart_descriptions.path_safety import (
    is_path_within_roots,
)
from transcriptx.core.analysis.chart_descriptions.schemas import SCHEMA_EVIDENCE


def load_evidence_for_chart(
    chart: LogicalChartDescriptor,
    *,
    run_root: Path,
    allowed_roots: list[Path],
) -> tuple[ChartEvidence | None, str | None, bool]:
    """Return (evidence, skip_reason, is_legacy_fallback).

    Prefer explicit evidence sidecar. Legacy fallback uses chart titles/labels
    only (never generated LLM outputs or arbitrary module JSON dumps).
    """
    run_root = Path(run_root)
    if chart.evidence_rel_path:
        base = run_root
        for rep in chart.representations:
            if rep.storage_root:
                base = Path(rep.storage_root)
                break
        path = base / chart.evidence_rel_path
        if not is_path_within_roots(path, allowed_roots + [base]):
            return None, "evidence_path_outside_roots", False
        if not path.is_file():
            return None, "evidence_missing", False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None, "evidence_unreadable", False
        evidence = parse_evidence_payload(payload if isinstance(payload, dict) else {})
        if evidence is None:
            return None, "evidence_schema_invalid", False
        if not evidence_within_caps(evidence):
            return None, "evidence_too_large", False
        if evidence.viz_id and evidence.viz_id != chart.viz_id:
            return None, "evidence_viz_mismatch", False
        if evidence.module and evidence.module != chart.module:
            return None, "evidence_module_mismatch", False
        return evidence, None, False

    # Legacy fallback: chart identity + registry help only (no module JSON scrape).
    evidence = ChartEvidence(
        schema_id=SCHEMA_EVIDENCE,
        viz_id=chart.viz_id,
        module=chart.module,
        scope=chart.scope,
        speaker=chart.speaker,
        title=chart.title,
        notes=chart.registry_description,
        transformations=["legacy_metadata_fallback"],
    )
    if not evidence_within_caps(evidence):
        return None, "evidence_too_large", True
    return evidence, None, True
