"""Deterministic in-transcript name / vocative extraction."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.identify.models import ChannelCandidate
from transcriptx.io.speaker_map_resolver import (
    normalize_diarized_id,
    normalize_display_name,
)

_STOP = frozenset(
    {
        "i",
        "im",
        "a",
        "an",
        "the",
        "yes",
        "yeah",
        "yep",
        "no",
        "nope",
        "ok",
        "okay",
        "right",
        "well",
        "so",
        "but",
        "and",
        "or",
        "if",
        "just",
        "like",
        "really",
        "actually",
        "um",
        "uh",
        "hello",
        "hi",
        "hey",
        "please",
        "sorry",
        "wait",
        "thanks",
        "thank",
        "you",
        "we",
        "they",
        "it",
        "this",
        "that",
        "here",
        "there",
        "everyone",
        "everybody",
        "someone",
        "somebody",
        "going",
        "gonna",
        "want",
        "need",
        "think",
        "know",
        "mean",
        "sure",
        "good",
        "great",
        "morning",
        "afternoon",
        "evening",
        "today",
        "now",
        "next",
        "first",
        "second",
        "all",
        "our",
        "your",
        "my",
        "me",
        "us",
        "not",
        "dont",
        "can't",
        "cannot",
        "can",
        "will",
        "would",
        "could",
        "should",
        "let",
        "lets",
        "got",
        "get",
        "one",
        "two",
        "three",
        "okay",
        "alright",
        "anyway",
        "maybe",
        "probably",
        "speaking",
        "name",
        "called",
        "team",
        "folks",
        "guys",
        "everyone",
    }
)

_NAME_TOKEN = r"[A-Za-z][A-Za-z'`-]{1,30}"
_NAME_GROUP = rf"({_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,2}})"

_SELF_INTRO_RE = re.compile(
    rf"\b(?:i(?:'m| am)|this is|my name is|i am called|i'm called)\s+"
    rf"{_NAME_GROUP}\b",
    re.IGNORECASE,
)
_VOCATIVE_RE = re.compile(
    rf"\b(?:thanks|thank you|hey|hi|hello|ok|okay)\s+{_NAME_GROUP}\b",
    re.IGNORECASE,
)
_LEADING_VOCATIVE_RE = re.compile(rf"^{_NAME_GROUP}\s*,", re.IGNORECASE)


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


def title_person_name(raw: str) -> str:
    """Normalise an extracted person name for display (Maya, Mary Jane)."""
    cleaned = re.sub(r"\s+", " ", str(raw or "").strip())
    cleaned = cleaned.strip(".,;:!?")
    parts = []
    for token in cleaned.split(" "):
        lowered = token.lower()
        if not token or lowered in _STOP:
            continue
        if not re.fullmatch(_NAME_TOKEN, token):
            return ""
        parts.append(token[:1].upper() + token[1:].lower())
    if not parts or len(parts) > 3:
        return ""
    return " ".join(parts)


def normalize_person_key(name: str) -> str:
    return normalize_display_name(name).casefold()


def _extract_names(pattern: re.Pattern[str], text: str) -> list[str]:
    out: list[str] = []
    for match in pattern.finditer(text):
        titled = title_person_name(match.group(1))
        if titled:
            out.append(titled)
    return out


def extract_mention_candidates(
    segments: Sequence[Mapping[str, Any]],
) -> dict[str, ChannelCandidate]:
    """Return unique-winner mention candidates keyed by diarized ID.

    Self-introductions vote for the speaking ID. Vocatives vote for the other
    speaker in two-party audio, or the adjacent other speaker when unique.
    """
    ordered: list[tuple[str, str]] = []
    speakers: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        speaker = _segment_speaker(segment)
        if not speaker:
            continue
        text = _segment_text(segment)
        ordered.append((speaker, text))
        if speaker not in seen:
            seen.add(speaker)
            speakers.append(speaker)

    votes: dict[str, Counter[str]] = defaultdict(Counter)
    evidence: dict[str, list[dict[str, str]]] = defaultdict(list)

    def vote(target: str, name: str, kind: str, text: str) -> None:
        if not target or not name:
            return
        votes[target][normalize_person_key(name)] += 1
        evidence[target].append({"kind": kind, "name": name, "text": text[:160]})

    other_of_two = None
    if len(speakers) == 2:
        other_of_two = {speakers[0]: speakers[1], speakers[1]: speakers[0]}

    for index, (speaker, text) in enumerate(ordered):
        if not text:
            continue
        for name in _extract_names(_SELF_INTRO_RE, text):
            vote(speaker, name, "self_intro", text)
        vocatives = _extract_names(_VOCATIVE_RE, text) + _extract_names(
            _LEADING_VOCATIVE_RE, text
        )
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
        if target:
            for name in vocatives:
                vote(target, name, "vocative", text)

    winners: dict[str, ChannelCandidate] = {}
    for speaker, counter in votes.items():
        if not counter:
            continue
        ranked = counter.most_common()
        best_key, best_count = ranked[0]
        if len(ranked) > 1 and ranked[1][1] == best_count:
            continue
        display = next(
            (
                row["name"]
                for row in evidence[speaker]
                if normalize_person_key(row["name"]) == best_key
            ),
            title_person_name(best_key),
        )
        if not display:
            continue
        winners[speaker] = ChannelCandidate(
            channel="mention",
            display_name=display,
            profile_id=None,
            score=float(best_count),
            confidence="strong" if best_count >= 2 else "possible",
            evidence={
                "vote_count": best_count,
                "samples": evidence[speaker][:8],
            },
        )
    return winners


def attach_profile_ids(
    candidates: dict[str, ChannelCandidate],
    *,
    profiles: Sequence[tuple[str, str]],
) -> dict[str, ChannelCandidate]:
    """If an extracted name uniquely matches a profile display name, attach id."""
    by_key: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for profile_id, display_name in profiles:
        key = normalize_person_key(display_name)
        if key:
            by_key[key].append((profile_id, display_name))
    out: dict[str, ChannelCandidate] = {}
    for speaker, cand in candidates.items():
        matches = by_key.get(normalize_person_key(cand.display_name), [])
        if len(matches) == 1:
            profile_id, display_name = matches[0]
            out[speaker] = ChannelCandidate(
                channel=cand.channel,
                display_name=display_name,
                profile_id=profile_id,
                score=cand.score,
                confidence=cand.confidence,
                evidence=dict(cand.evidence) | {"profile_name_match": True},
            )
        else:
            out[speaker] = cand
    return out
