"""Resolve deterministic insights + highlight quotes for B18 narrative input."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from transcriptx.core.analysis.highlights.post_process import highlight_quote_text_by_id
from transcriptx.core.analysis.llm_module_errors import (
    ModuleDependencyMissingError,
    ModuleEmptyInputError,
)

_INSIGHTS_CANONICAL = "insights/data/global/{base}_insights.json"


def _canonical_insights_rel(base_name: str) -> str:
    return _INSIGHTS_CANONICAL.format(base=base_name)


def _load_insights_payload(transcript_dir: Path, base_name: str) -> Dict[str, Any]:
    rel = _canonical_insights_rel(base_name)
    path = transcript_dir / rel
    if not path.is_file():
        raise ModuleDependencyMissingError(
            "insights artifact is required for insights_narrative"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModuleDependencyMissingError(f"insights artifact unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise ModuleDependencyMissingError("insights artifact is not a JSON object")
    return payload


def _load_highlights_payload(
    context: Any,
    base_name: str,
) -> Dict[str, Any]:
    stored = context.get_analysis_result("highlights")
    if isinstance(stored, dict):
        return stored
    rel = f"highlights/data/global/{base_name}_highlights.json"
    path = context.get_transcript_dir() / rel
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except (OSError, json.JSONDecodeError):
            pass
    raise ModuleDependencyMissingError(
        "highlights artifact is required for insights_narrative quote resolution"
    )


def _quote_map(highlights: Dict[str, Any]) -> Dict[str, str]:
    return highlight_quote_text_by_id(highlights)


def build_narrative_input(
    insights: Dict[str, Any],
    highlights: Dict[str, Any],
    *,
    max_themes: int = 8,
) -> Dict[str, Any]:
    if str(insights.get("status") or "ok") != "ok":
        raise ModuleEmptyInputError("insights status is not ok for narrative generation")
    quotes = _quote_map(highlights)
    themes_out: List[Dict[str, Any]] = []
    for row in list(insights.get("key_themes") or [])[:max_themes]:
        if not isinstance(row, dict):
            continue
        phrase = str(row.get("phrase") or "").strip()
        if not phrase:
            continue
        evidence = []
        for qid in row.get("evidence_quote_ids") or []:
            text = quotes.get(str(qid), "").strip()
            if text:
                evidence.append({"quote_id": str(qid), "quote": text})
        themes_out.append(
            {
                "phrase": phrase,
                "confidence": row.get("confidence"),
                "evidence": evidence,
            }
        )
    ideas_out: List[str] = []
    for row in list(insights.get("recurring_ideas") or [])[:max_themes]:
        if isinstance(row, dict):
            phrase = str(row.get("phrase") or "").strip()
            if phrase:
                ideas_out.append(phrase)
    if not themes_out:
        raise ModuleEmptyInputError("no evidenced themes for narrative generation")
    return {"key_themes": themes_out, "recurring_ideas": ideas_out}


def resolve_insights_narrative_inputs(context: Any) -> Dict[str, Any]:
    base_name = context.get_base_name()
    insights = _load_insights_payload(context.get_transcript_dir(), base_name)
    highlights = _load_highlights_payload(context, base_name)
    return build_narrative_input(insights, highlights)


def serialise_narrative_input(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str)
