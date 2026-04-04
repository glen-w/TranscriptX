"""
Edge-pooled contagion merge for group aggregation (canonical directed pairs).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Set, Tuple

from transcriptx.core.analysis.aggregation.rows import (
    _build_display_to_canonical,
    _fallback_canonical_id,
)
from transcriptx.core.analysis.aggregation.warnings import build_warning
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _extract_contagion_payload(module_results: Dict[str, Any]) -> Dict[str, Any]:
    result = module_results.get("contagion", {})
    if not isinstance(result, dict):
        return {}
    payload = result.get("payload") or result.get("results") or {}
    return payload if isinstance(payload, dict) else {}


def build_contagion_pooled_for_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Merge per-transcript ``contagion_summary`` into ``contagion_pooled``.

    Returns ``(contagion_pooled, aggregation_warnings)``. Warnings are non-fatal;
    the parent runner appends them without skipping row output.
    """
    edge_emotions: Dict[Tuple[int, int], Counter[str]] = defaultdict(Counter)
    observed_display: Dict[int, Set[str]] = defaultdict(set)
    warnings: List[Dict[str, Any]] = []

    for result in per_transcript_results:
        if "contagion" not in result.module_results:
            continue
        payload = _extract_contagion_payload(result.module_results)
        if not payload:
            continue
        summary = payload.get("contagion_summary") or {}
        if not isinstance(summary, dict):
            continue

        display_to_canonical = _build_display_to_canonical(
            result.transcript_path, canonical_speaker_map
        )
        transcript_label = str(result.transcript_path)

        for raw_key, emotion_counts in summary.items():
            if not isinstance(raw_key, str):
                continue
            parts = raw_key.split("->", 1)
            if len(parts) != 2:
                warnings.append(
                    build_warning(
                        code="RELATIONAL_POOL_PARSE",
                        message='Invalid contagion pair key (expected "From->To").',
                        aggregation_key="contagion",
                        transcripts_affected=[transcript_label],
                        details={"key": raw_key[:200]},
                    )
                )
                continue
            from_disp, to_disp = parts[0].strip(), parts[1].strip()
            if not from_disp or not to_disp:
                warnings.append(
                    build_warning(
                        code="RELATIONAL_POOL_PARSE",
                        message="Empty endpoint in contagion pair key.",
                        aggregation_key="contagion",
                        transcripts_affected=[transcript_label],
                        details={"key": raw_key[:200]},
                    )
                )
                continue

            fc = display_to_canonical.get(from_disp, _fallback_canonical_id(from_disp))
            tc = display_to_canonical.get(to_disp, _fallback_canonical_id(to_disp))

            if fc == tc:
                warnings.append(
                    build_warning(
                        code="RELATIONAL_POOL_SELF_EDGE",
                        message="Dropped self-edge in contagion pooled merge.",
                        aggregation_key="contagion",
                        transcripts_affected=[transcript_label],
                        details={"from_canonical": fc, "key": raw_key[:200]},
                    )
                )
                continue

            observed_display[fc].add(from_disp)
            observed_display[tc].add(to_disp)

            if not isinstance(emotion_counts, dict):
                continue
            for emo, raw_count in emotion_counts.items():
                if emo is None:
                    continue
                try:
                    c = int(raw_count)
                except (TypeError, ValueError):
                    continue
                if c <= 0:
                    continue
                edge_emotions[(fc, tc)][str(emo)] += c

    edges: List[Dict[str, Any]] = []
    for (fc, tc), ctr in sorted(
        edge_emotions.items(), key=lambda kv: (kv[0][0], kv[0][1])
    ):
        emotions_map = dict(sorted(ctr.items()))
        total = sum(emotions_map.values())
        if total <= 0:
            continue
        from_display = canonical_speaker_map.canonical_to_display.get(fc)
        if not from_display and observed_display[fc]:
            from_display = min(observed_display[fc])
        if not from_display:
            from_display = str(fc)
        to_display = canonical_speaker_map.canonical_to_display.get(tc)
        if not to_display and observed_display[tc]:
            to_display = min(observed_display[tc])
        if not to_display:
            to_display = str(tc)

        edges.append(
            {
                "from_canonical_id": fc,
                "to_canonical_id": tc,
                "from_display": from_display,
                "to_display": to_display,
                "emotions": emotions_map,
                "total": total,
            }
        )

    edges.sort(
        key=lambda e: (-int(e["total"]), e["from_canonical_id"], e["to_canonical_id"])
    )

    contagion_pooled: Dict[str, Any] = {"schema_version": 1, "edges": edges}
    return contagion_pooled, warnings
