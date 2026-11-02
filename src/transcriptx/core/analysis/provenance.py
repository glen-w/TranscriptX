"""Shared evidence / provenance envelope (P2).

First adopters: insights schema-v3 rows, highlights theme groups, llm_action_items
records. This is not a new analysis module ID.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

PROVENANCE_SCHEMA_ID = "transcriptx.evidence_provenance.v1"
CONFIDENCE_VALUES = frozenset({"high", "medium", "low"})


def evidence_provenance(
    *,
    source_module: str,
    quote_ids: Sequence[str] | None = None,
    confidence: str | None = None,
    abstention: Mapping[str, Any] | None = None,
    spans: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the shared P2 envelope.

    ``quote_ids`` are existing highlight / stable quote ids (not invented).
    ``spans`` are optional {start, end, text?} dicts. Empty lists mean "no
    attached evidence", not missing infrastructure.
    """
    conf = str(confidence).strip().lower() if confidence else None
    if conf and conf not in CONFIDENCE_VALUES:
        conf = None
    quotes = [str(q) for q in (quote_ids or []) if str(q).strip()]
    span_rows = [dict(s) for s in (spans or []) if isinstance(s, Mapping)]
    abs_payload = dict(abstention) if isinstance(abstention, Mapping) else None
    return {
        "schema_id": PROVENANCE_SCHEMA_ID,
        "source_module": str(source_module),
        "quote_ids": quotes,
        "confidence": conf,
        "abstention": abs_payload,
        "spans": span_rows,
    }


def attach_provenance(
    row: dict[str, Any], envelope: Mapping[str, Any]
) -> dict[str, Any]:
    """Return a shallow copy of ``row`` with ``provenance`` set."""
    out = dict(row)
    out["provenance"] = dict(envelope)
    return out
