"""Deterministic per-speaker name options (no LLM)."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.identify.mentions import (
    extract_self_intro_names,
    extract_vocative_names,
    normalize_person_key,
    title_person_name,
)
from transcriptx.core.speaker_profiles.identify.suggestions.models import (
    NameOption,
    RosterPerson,
)
from transcriptx.io.speaker_map_resolver import normalize_diarized_id

_MAX_OPTIONS = 8
_EARLY_TURN_LIMIT = 12
_MODERATOR_LIST_RE = re.compile(
    r"\b(?:first|next|then|now|please welcome|joined by|with us|we have)\b",
    re.IGNORECASE,
)


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


def _ordered_segments(
    segments: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[tuple[str, str]]]:
    speakers: list[str] = []
    seen: set[str] = set()
    ordered: list[tuple[str, str]] = []
    for segment in segments:
        if not isinstance(segment, Mapping):
            continue
        speaker = _segment_speaker(segment)
        if not speaker:
            continue
        text = _segment_text(segment)
        ordered.append((speaker, text))
        if speaker not in seen:
            seen.add(speaker)
            speakers.append(speaker)
    return speakers, ordered


def _roster_names_in_text(text: str, roster: Sequence[RosterPerson]) -> list[str]:
    """Return roster display names in order of first appearance in text."""
    if not text:
        return []
    lower = text.casefold()
    found: list[str] = []
    seen: set[str] = set()
    for person in sorted(roster, key=lambda p: len(p.display_name), reverse=True):
        key = person.normalized_key
        if key in seen:
            continue
        if person.display_name.casefold() in lower:
            found.append(person.display_name)
            seen.add(key)
    return found


def _moderator_assignments(
    speakers: list[str],
    ordered: list[tuple[str, str]],
    roster: Sequence[RosterPerson],
) -> dict[str, NameOption]:
    """Map non-moderator speakers to names listed by a moderator in early turns."""
    if len(speakers) < 3 or not roster:
        return {}
    early_by_speaker: dict[str, list[str]] = {s: [] for s in speakers}
    counts: dict[str, int] = {s: 0 for s in speakers}
    for speaker, text in ordered[: _EARLY_TURN_LIMIT * len(speakers)]:
        names = _roster_names_in_text(text, roster)
        if len(names) >= 2 or (
            len(names) >= 1 and _MODERATOR_LIST_RE.search(text or "")
        ):
            for name in names:
                if name not in early_by_speaker[speaker]:
                    early_by_speaker[speaker].append(name)
            counts[speaker] = len(early_by_speaker[speaker])

    moderator = max(counts, key=lambda s: counts[s])
    if counts[moderator] < 2:
        return {}

    listed = early_by_speaker[moderator]
    others = [s for s in speakers if s != moderator]
    if len(listed) != len(others):
        return {}

    quote = ""
    for spk, text in ordered:
        if spk == moderator and _roster_names_in_text(text, roster):
            quote = text[:160]
            break

    out: dict[str, NameOption] = {}
    for speaker, name in zip(others, listed):
        out[speaker] = NameOption(
            display_name=name,
            basis="moderator_list",
            confidence="possible",
            quote=quote,
        )
    return out


def _add_crm_options(
    per_speaker: dict[str, list[NameOption]],
    seen_per: dict[str, set[str]],
    roster: Sequence[RosterPerson],
) -> None:
    from transcriptx.core.speaker_profiles.identify.settings import (
        load_identify_settings,
    )
    from transcriptx.core.speaker_profiles.identify.twenty import (
        get_people_index,
        unique_crm_person,
    )

    ident = load_identify_settings()
    if not ident.twenty_enabled or ident.twenty_role == "off":
        return
    index = get_people_index(ident)
    if index is None or not index.people:
        return
    conf = "likely" if ident.twenty_role == "gate" else "possible"
    for speaker, bucket in per_speaker.items():
        local = [o.display_name for o in bucket]
        local.extend(
            p.display_name for p in roster if speaker in p.mentioned_by_speakers
        )
        seen_hits: set[str] = set()
        for name in local:
            hit = unique_crm_person(name, index)
            if hit is None:
                continue
            display = hit.identity_name()
            key = normalize_person_key(display)
            if not key or key in seen_hits:
                continue
            seen_hits.add(key)
            _add_option(
                bucket,
                seen_per[speaker],
                NameOption(
                    display_name=display,
                    basis="crm",
                    confidence=conf,  # type: ignore[arg-type]
                    quote="Twenty CRM people record",
                ),
            )


def _add_option(
    bucket: list[NameOption],
    seen: set[str],
    option: NameOption,
) -> None:
    key = normalize_person_key(option.display_name)
    if not key or key in seen:
        return
    seen.add(key)
    bucket.append(option)


def build_deterministic_options(
    segments: Sequence[Mapping[str, Any]],
    roster: Sequence[RosterPerson],
) -> dict[str, tuple[NameOption, ...]]:
    """Ranked name options per diarized speaker."""
    speakers, ordered = _ordered_segments(segments)
    if not speakers:
        return {}

    moderator_opts = _moderator_assignments(speakers, ordered, roster)
    other_of_two = None
    if len(speakers) == 2:
        other_of_two = {speakers[0]: speakers[1], speakers[1]: speakers[0]}

    per_speaker: dict[str, list[NameOption]] = {s: [] for s in speakers}
    seen_per: dict[str, set[str]] = {s: set() for s in speakers}

    for speaker in speakers:
        if speaker in moderator_opts:
            _add_option(
                per_speaker[speaker], seen_per[speaker], moderator_opts[speaker]
            )

    for speaker, text in ordered:
        if not text:
            continue
        for name in extract_self_intro_names(text):
            _add_option(
                per_speaker[speaker],
                seen_per[speaker],
                NameOption(
                    display_name=name,
                    basis="self_intro",
                    confidence="strong",
                    quote=text[:160],
                ),
            )

    for index, (speaker, text) in enumerate(ordered):
        vocatives = extract_vocative_names(text)
        if not vocatives:
            continue
        target = None
        if other_of_two is not None:
            target = other_of_two.get(speaker)
        else:
            neighbours: list[str] = []
            if index > 0 and ordered[index - 1][0] != speaker:
                neighbours.append(ordered[index - 1][0])
            if index + 1 < len(ordered) and ordered[index + 1][0] != speaker:
                neighbours.append(ordered[index + 1][0])
            unique = list(dict.fromkeys(neighbours))
            if len(unique) == 1:
                target = unique[0]
        if not target:
            continue
        for name in vocatives:
            titled = title_person_name(name)
            if not titled:
                continue
            _add_option(
                per_speaker[target],
                seen_per[target],
                NameOption(
                    display_name=titled,
                    basis="vocative",
                    confidence="possible",
                    quote=text[:160],
                ),
            )

    for person in roster:
        for speaker in speakers:
            if speaker in person.mentioned_by_speakers:
                _add_option(
                    per_speaker[speaker],
                    seen_per[speaker],
                    NameOption(
                        display_name=person.display_name,
                        basis="roster",
                        confidence="possible",
                        quote=person.sample_quote,
                    ),
                )

    # Global roster fallbacks (pick any person in the room)
    for speaker in speakers:
        for person in roster[:5]:
            _add_option(
                per_speaker[speaker],
                seen_per[speaker],
                NameOption(
                    display_name=person.display_name,
                    basis="roster",
                    confidence="possible",
                    quote=person.sample_quote,
                ),
            )

    _add_crm_options(per_speaker, seen_per, roster)

    def rank_key(opt: NameOption) -> tuple[int, int, str]:
        order = {
            "self_intro": 0,
            "moderator_list": 1,
            "crm": 2,
            "vocative": 3,
            "roster": 4,
        }
        conf = {"strong": 0, "likely": 1, "possible": 2}
        return (order.get(opt.basis, 5), conf.get(opt.confidence, 3), opt.display_name)

    out: dict[str, tuple[NameOption, ...]] = {}
    for speaker in speakers:
        opts = sorted(per_speaker[speaker], key=rank_key)[:_MAX_OPTIONS]
        out[speaker] = tuple(opts)
    return out
