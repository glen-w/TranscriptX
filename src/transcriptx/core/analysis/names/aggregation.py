"""Group aggregation for the names (people mentioned) module."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def aggregate_names_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Pool per-transcript people catalogs into session rows + a group pooled view."""
    from transcriptx.core.analysis.aggregation.registry import (
        _extract_payload,
        _session_row_base,
        _warning_payload_shape,
    )

    session_rows: List[Dict[str, Any]] = []
    pooled: dict[str, dict[str, Any]] = {}

    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "names")
        if not payload:
            continue
        if not isinstance(payload, dict):
            return _warning_payload_shape("names", ["people", "global_stats"])
        global_stats = payload.get("global_stats") or {}
        people = payload.get("people") or []
        if not isinstance(global_stats, dict) or not isinstance(people, list):
            return _warning_payload_shape("names", ["people", "global_stats"])

        session_row = _session_row_base(result, transcript_set)
        session_row["unique_people"] = global_stats.get("unique_people")
        session_row["total_mentions"] = global_stats.get("total_mentions")
        session_rows.append(session_row)

        for person in people:
            if not isinstance(person, dict):
                continue
            key = str(person.get("normalized_key") or "").strip()
            if not key:
                continue
            entry = pooled.get(key)
            if entry is None:
                entry = {
                    "display_name": person.get("display_name") or key,
                    "normalized_key": key,
                    "mention_count": 0,
                    "session_count": 0,
                    "mentioned_by_speakers": set(),
                }
                pooled[key] = entry
            mention_count = person.get("mention_count")
            if isinstance(mention_count, (int, float)):
                entry["mention_count"] += int(mention_count)
            entry["session_count"] += 1
            for speaker in person.get("mentioned_by_speakers") or []:
                if speaker:
                    entry["mentioned_by_speakers"].add(str(speaker))

    if not session_rows:
        return None

    top_people = sorted(
        (
            {
                "display_name": entry["display_name"],
                "normalized_key": entry["normalized_key"],
                "mention_count": int(entry["mention_count"]),
                "session_count": int(entry["session_count"]),
                "mentioned_by_speakers": sorted(entry["mentioned_by_speakers"]),
            }
            for entry in pooled.values()
        ),
        key=lambda row: (-row["mention_count"], str(row["display_name"]).casefold()),
    )
    names_pooled = {
        "schema_version": 1,
        "unique_people": len(top_people),
        "total_mentions": sum(row["mention_count"] for row in top_people),
        "top_people": top_people[:50],
    }
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "names_pooled": names_pooled,
    }
