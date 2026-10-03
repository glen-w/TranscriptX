"""Group aggregation for the names (people mentioned) module."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def aggregate_names(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Pool people catalogs across transcripts by normalized_key."""
    from transcriptx.core.analysis.aggregation.registry import (
        _extract_payload,
        _warning_payload_shape,
    )
    from transcriptx.core.analysis.aggregation.rows import session_row_from_result
    from transcriptx.core.analysis.aggregation.schema import get_transcript_id
    from transcriptx.core.analysis.names.schema import SCHEMA_ID

    session_rows: List[Dict[str, Any]] = []
    pool: dict[str, dict[str, Any]] = {}

    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "names")
        if not payload:
            continue
        if not isinstance(payload, dict):
            return _warning_payload_shape("names", ["people", "global_stats"])
        metadata = payload.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("schema_id") not in (
            None,
            SCHEMA_ID,
        ):
            continue
        global_stats = payload.get("global_stats") or {}
        if not isinstance(global_stats, dict):
            return _warning_payload_shape("names", ["people", "global_stats"])
        session_rows.append(
            session_row_from_result(
                result,
                transcript_set,
                usable=payload.get("usable"),
                unique_people=global_stats.get("unique_people"),
                total_mentions=global_stats.get("total_mentions"),
            )
        )
        member_id = str(get_transcript_id(result, transcript_set))
        people = payload.get("people") or []
        if not isinstance(people, list):
            continue
        for person in people:
            if not isinstance(person, dict):
                continue
            key = str(person.get("normalized_key") or "").strip()
            if not key:
                continue
            entry = pool.setdefault(
                key,
                {
                    "display_name": str(person.get("display_name") or key),
                    "normalized_key": key,
                    "mention_count": 0,
                    "mentioned_by_speakers": set(),
                    "member_ids": set(),
                },
            )
            entry["mention_count"] += int(person.get("mention_count") or 0)
            for speaker in person.get("mentioned_by_speakers") or []:
                if speaker:
                    entry["mentioned_by_speakers"].add(str(speaker))
            if member_id:
                entry["member_ids"].add(member_id)
            display = str(person.get("display_name") or "").strip()
            if display and len(display) > len(str(entry["display_name"])):
                # Prefer a longer surface as the shared display label.
                entry["display_name"] = display

    if not session_rows:
        return None

    people_rows = [
        {
            "display_name": entry["display_name"],
            "normalized_key": entry["normalized_key"],
            "mention_count": entry["mention_count"],
            "mentioned_by_speakers": sorted(entry["mentioned_by_speakers"]),
            "member_count": len(entry["member_ids"]),
        }
        for entry in pool.values()
    ]
    people_rows.sort(
        key=lambda row: (-int(row["mention_count"]), str(row["display_name"]).casefold())
    )
    pooled = {
        "schema_version": 1,
        "unique_people": len(people_rows),
        "total_mentions": sum(int(row["mention_count"]) for row in people_rows),
        "top_people": people_rows[:50],
    }
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "names_pooled": pooled,
    }
