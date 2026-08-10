"""
Group aggregation for the insights module.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.aggregation.common import extract_payload
from transcriptx.core.analysis.aggregation.rows import _session_row_base
from transcriptx.core.analysis.aggregation.schema import get_transcript_id
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _artifact_relpath(result: Dict[str, Any], needle: str) -> Optional[str]:
    artifacts = result.get("artifacts") or []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        rel = artifact.get("relative_path") or artifact.get("path")
        if isinstance(rel, str) and needle in rel and rel.endswith(".json"):
            return rel
    return None


def _theme_score(item: Dict[str, Any]) -> float | None:
    score = item.get("score")
    if isinstance(score, dict):
        total = score.get("total")
        if total is not None:
            try:
                return float(total)
            except (TypeError, ValueError):
                return None
    if score is None:
        return None
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def aggregate_insights_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Aggregate key themes, recurring ideas, and notable moments across sessions."""
    del canonical_speaker_map
    session_rows: List[Dict[str, Any]] = []
    content_rows: List[Dict[str, Any]] = []

    for result in per_transcript_results:
        payload = extract_payload(result.module_results, "insights")
        if not payload:
            continue
        transcript_id = get_transcript_id(result, transcript_set)
        key_themes = payload.get("key_themes") or []
        recurring_ideas = payload.get("recurring_ideas") or []
        notable_moments = payload.get("notable_moments") or []
        if not isinstance(key_themes, list):
            key_themes = []
        if not isinstance(recurring_ideas, list):
            recurring_ideas = []
        if not isinstance(notable_moments, list):
            notable_moments = []

        session_row = _session_row_base(result, transcript_set)
        session_row["theme_count"] = len(
            [row for row in key_themes if isinstance(row, dict)]
        )
        session_row["recurring_idea_count"] = len(
            [row for row in recurring_ideas if isinstance(row, dict)]
        )
        session_row["notable_moment_count"] = len(
            [row for row in notable_moments if isinstance(row, dict)]
        )
        session_row["insights_status"] = str(payload.get("status") or "ok")
        session_rows.append(session_row)

        source_rel = _artifact_relpath(
            result.module_results.get("insights", {}), "insights"
        )

        for kind, items in (
            ("key_theme", key_themes),
            ("recurring_idea", recurring_ideas),
        ):
            for item in items:
                if not isinstance(item, dict):
                    continue
                phrase = str(item.get("phrase") or item.get("text") or "")
                if not phrase:
                    continue
                score = _theme_score(item)
                hash_payload = f"{transcript_id}:{kind}:{phrase[:200]}"
                content_rows.append(
                    {
                        "id": hashlib.sha1(hash_payload.encode("utf-8")).hexdigest(),
                        "order_index": result.order_index,
                        "kind": kind,
                        "text": phrase,
                        "score": score,
                        "confidence": item.get("confidence"),
                        "source_transcript_id": transcript_id,
                        "source_run_relpath": result.output_dir,
                        "source_artifact_relpath": source_rel,
                    }
                )

        for item in notable_moments:
            if not isinstance(item, dict):
                continue
            text = str(item.get("quote") or item.get("text") or "")
            start = item.get("start")
            end = item.get("end")
            score_dict = item.get("score") or {}
            score = None
            if isinstance(score_dict, dict):
                score = score_dict.get("total")
            hash_payload = f"{transcript_id}:moment:{start}:{end}:{text[:200]}"
            content_rows.append(
                {
                    "id": hashlib.sha1(hash_payload.encode("utf-8")).hexdigest(),
                    "order_index": result.order_index,
                    "kind": "notable_moment",
                    "text": text,
                    "score": score,
                    "start_time": start,
                    "end_time": end,
                    "speaker": item.get("speaker"),
                    "source_transcript_id": transcript_id,
                    "source_run_relpath": result.output_dir,
                    "source_artifact_relpath": source_rel,
                }
            )

    if not session_rows and not content_rows:
        return None
    content_rows.sort(
        key=lambda row: (
            row.get("order_index", 0),
            str(row.get("kind") or ""),
            -(row.get("score") or 0),
        )
    )
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "content_rows": content_rows,
        "content_rows_name": "insight_rows",
        "metrics_spec": [
            {
                "name": "theme_count",
                "format": "int",
                "description": "Key themes in session",
            },
            {
                "name": "score",
                "format": "float",
                "description": "Insight item score",
            },
        ],
    }
