"""Build a people roster from spaCy PERSON entities."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from transcriptx.core.analysis.names.catalog import build_names_catalog
from transcriptx.core.analysis.ner import extract_named_entities
from transcriptx.core.speaker_profiles.identify.mentions import (
    normalize_person_key,
    title_person_name,
)
from transcriptx.core.speaker_profiles.identify.suggestions.models import RosterPerson
from transcriptx.io.speaker_map_resolver import normalize_diarized_id


def _segment_text(segment: Mapping[str, Any]) -> str:
    raw = segment.get("text")
    if raw is None:
        raw = segment.get("transcript")
    return str(raw or "").strip()


def _segment_speaker(segment: Mapping[str, Any]) -> str:
    raw = segment.get("speaker_diarized_id")
    if raw is None or str(raw).strip() == "":
        raw = segment.get("speaker")
    return normalize_diarized_id(raw)


def collect_person_mentions(
    segments: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Run spaCy NER per segment; return PERSON rows with diarized speaker ids."""
    person_mentions: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping):
            continue
        speaker = _segment_speaker(segment)
        text = _segment_text(segment)
        if not text:
            continue
        start_raw = segment.get("start")
        try:
            start_val: float | None = (
                float(start_raw) if start_raw is not None else None
            )
        except (TypeError, ValueError):
            start_val = None
        for ent_text, label in extract_named_entities(text):
            if label != "PERSON":
                continue
            titled = title_person_name(ent_text, apply_gazetteer=False)
            if not titled:
                continue
            person_mentions.append(
                {
                    "segment_index": index,
                    "start": start_val,
                    "speaker": speaker,
                    "text": text,
                    "surface": ent_text,
                }
            )
    return person_mentions


def build_roster(
    segments: Sequence[Mapping[str, Any]],
    *,
    min_mentions: int = 1,
) -> tuple[RosterPerson, ...]:
    """Aggregate PERSON entities into a filtered people roster."""
    mentions = collect_person_mentions(segments)
    catalog = build_names_catalog(
        mentions,
        segments=segments,
        min_mentions=min_mentions,
        exclude_known_speakers=False,
    )
    people = catalog.get("people") or []
    roster: list[RosterPerson] = []
    for row in people:
        if not isinstance(row, dict):
            continue
        display = title_person_name(
            str(row.get("display_name") or ""), apply_gazetteer=False
        )
        if not display:
            continue
        key = normalize_person_key(display)
        if not key:
            continue
        alias_keys = tuple(
            str(x).casefold() for x in (row.get("alias_keys") or ()) if str(x).strip()
        )
        sample = ""
        for mention in row.get("mentions") or []:
            if isinstance(mention, dict) and mention.get("text"):
                sample = str(mention["text"])[:160]
                break
        roster.append(
            RosterPerson(
                display_name=display,
                normalized_key=key,
                mention_count=int(row.get("mention_count") or 0),
                mentioned_by_speakers=tuple(
                    str(x)
                    for x in (row.get("mentioned_by_speakers") or ())
                    if str(x).strip()
                ),
                sample_quote=sample,
                alias_keys=alias_keys,
            )
        )
    roster.sort(key=lambda p: (-p.mention_count, p.display_name))
    return tuple(roster)


def allowed_name_keys(
    roster: Sequence[RosterPerson],
    segments: Sequence[Mapping[str, Any]],
) -> set[str]:
    """Names the LLM may assign: roster keys plus regex self-intros."""
    from transcriptx.core.speaker_profiles.identify.mentions import (
        extract_self_intro_names,
    )

    keys = {p.normalized_key for p in roster}
    for person in roster:
        keys.update(person.alias_keys)
    for segment in segments:
        if not isinstance(segment, Mapping):
            continue
        text = _segment_text(segment)
        for name in extract_self_intro_names(text):
            keys.add(normalize_person_key(name))
    return keys
