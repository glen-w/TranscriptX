"""Build a deduplicated people catalog from NER person mentions."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from transcriptx.core.analysis.entity_sentiment import normalize_entity_name
from transcriptx.utils.text_utils import is_named_speaker


def _normalized_key(name: str) -> str:
    return normalize_entity_name(name).casefold()


def _collect_known_speaker_names(segments: Sequence[Mapping[str, Any]]) -> set[str]:
    names: set[str] = set()
    for segment in segments:
        if not isinstance(segment, Mapping):
            continue
        speaker = segment.get("speaker")
        if speaker and is_named_speaker(str(speaker)):
            names.add(_normalized_key(str(speaker)))
    return names


def build_names_catalog(
    person_mentions: Sequence[Mapping[str, Any]],
    *,
    segments: Sequence[Mapping[str, Any]] | None = None,
    min_mentions: int = 1,
    exclude_known_speakers: bool = False,
    max_mentions_per_person: int = 50,
) -> dict[str, Any]:
    """Aggregate spaCy PERSON mentions into a transcript-wide people catalog."""
    known_speakers = (
        _collect_known_speaker_names(segments or ())
        if exclude_known_speakers
        else set()
    )

    grouped: dict[str, dict[str, Any]] = {}
    for raw in person_mentions:
        if not isinstance(raw, Mapping):
            continue
        surface = str(raw.get("surface") or "").strip()
        if not surface:
            continue
        display_name = normalize_entity_name(surface)
        key = _normalized_key(display_name)
        if not key:
            continue
        if exclude_known_speakers and key in known_speakers:
            continue

        entry = grouped.get(key)
        if entry is None:
            entry = {
                "display_name": display_name,
                "normalized_key": key,
                "mention_count": 0,
                "mentioned_by_speakers": set(),
                "mentions": [],
            }
            grouped[key] = entry

        entry["mention_count"] += 1
        speaker = str(raw.get("speaker") or "").strip()
        if speaker:
            entry["mentioned_by_speakers"].add(speaker)
        entry["mentions"].append(
            {
                "segment_index": raw.get("segment_index"),
                "start": raw.get("start"),
                "speaker": speaker,
                "text": str(raw.get("text") or ""),
                "surface": surface,
            }
        )

    people: list[dict[str, Any]] = []
    for entry in grouped.values():
        if entry["mention_count"] < min_mentions:
            continue
        mentions = sorted(
            entry["mentions"],
            key=lambda row: (
                row.get("segment_index") is None,
                row.get("segment_index") if row.get("segment_index") is not None else 0,
            ),
        )
        people.append(
            {
                "display_name": entry["display_name"],
                "normalized_key": entry["normalized_key"],
                "mention_count": entry["mention_count"],
                "mentioned_by_speakers": sorted(entry["mentioned_by_speakers"]),
                "mentions": mentions[:max_mentions_per_person],
            }
        )

    people.sort(key=lambda row: (-row["mention_count"], row["display_name"].casefold()))
    total_mentions = sum(person["mention_count"] for person in people)
    return {
        "people": people,
        "global_stats": {
            "unique_people": len(people),
            "total_mentions": total_mentions,
        },
    }
