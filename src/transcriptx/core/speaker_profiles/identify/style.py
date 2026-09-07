"""Speech-pattern (style) vectors for returning-speaker corroboration."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.identify.models import ChannelCandidate
from transcriptx.core.utils.similarity_utils import extract_vocabulary_patterns
from transcriptx.io.speaker_map_resolver import normalize_diarized_id

FUNCTION_WORDS = (
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "as",
    "at",
    "by",
    "from",
    "that",
    "this",
    "it",
    "is",
    "was",
    "were",
    "be",
    "been",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "not",
    "so",
    "just",
    "like",
    "really",
    "actually",
    "well",
    "you",
    "we",
    "they",
    "i",
    "me",
    "my",
    "um",
    "uh",
)

_WORD_RE = re.compile(r"[A-Za-z']+")
# Provisional: style-only apply stays off by default; this tau is conservative.
STYLE_STRONG_MIN = 0.88
STYLE_MARGIN = 0.05
MIN_WORDS = 12


def _segment_text(segment: Mapping[str, Any]) -> str:
    return str(segment.get("text") or segment.get("transcript") or "").strip()


def _speaker_of(segment: Mapping[str, Any]) -> str:
    raw = segment.get("speaker_diarized_id")
    if raw is None or str(raw).strip() == "":
        raw = segment.get("speaker")
    return normalize_diarized_id(raw)


def texts_for_speaker(
    segments: Sequence[Mapping[str, Any]], local_speaker_key: str
) -> list[str]:
    key = normalize_diarized_id(local_speaker_key)
    out: list[str] = []
    for segment in segments:
        if _speaker_of(segment) != key:
            continue
        text = _segment_text(segment)
        if text:
            out.append(text)
    return out


def build_style_vector(texts: Sequence[str]) -> dict[str, Any] | None:
    """Cheap per-speaker style vector from this transcript's lines."""
    if not texts:
        return None
    words: list[str] = []
    question_turns = 0
    for text in texts:
        tokens = [t.lower() for t in _WORD_RE.findall(text)]
        words.extend(tokens)
        if "?" in text:
            question_turns += 1
    if len(words) < MIN_WORDS:
        return None
    counts = Counter(words)
    total = float(len(words))
    function_rates = {w: counts.get(w, 0) / total for w in FUNCTION_WORDS}
    turn_words = [len(_WORD_RE.findall(t)) for t in texts]
    avg_turn = sum(turn_words) / max(len(turn_words), 1)
    return {
        "function_rates": function_rates,
        "avg_turn_words": avg_turn,
        "question_rate": question_turns / max(len(texts), 1),
        "word_count": len(words),
        "vocabulary_patterns": extract_vocabulary_patterns(list(texts)),
    }


def _cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 0.0
    dot = 0.0
    n1 = 0.0
    n2 = 0.0
    for key in keys:
        a = float(left.get(key, 0.0))
        b = float(right.get(key, 0.0))
        dot += a * b
        n1 += a * a
        n2 += b * b
    if n1 <= 0 or n2 <= 0:
        return 0.0
    return dot / math.sqrt(n1 * n2)


def style_similarity(query: Mapping[str, Any], ref: Mapping[str, Any]) -> float:
    fw = _cosine(query.get("function_rates") or {}, ref.get("function_rates") or {})
    q_turn = float(query.get("avg_turn_words") or 0.0)
    r_turn = float(ref.get("avg_turn_words") or 0.0)
    turn = 1.0 - min(abs(q_turn - r_turn) / max(q_turn, r_turn, 1.0), 1.0)
    q_q = float(query.get("question_rate") or 0.0)
    r_q = float(ref.get("question_rate") or 0.0)
    qsim = 1.0 - abs(q_q - r_q)
    return 0.6 * fw + 0.2 * turn + 0.2 * qsim


def collect_profile_style_refs(
    *,
    root: Path,
    exclude_managed_id: str | None = None,
    resolver=None,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Build style vectors from prior named/linked transcript text."""
    from transcriptx.core.speaker_profiles.aggregates import (
        list_profile_links,
        list_profiles,
    )
    from transcriptx.core.speaker_profiles.resolver import (
        ManagedTranscriptResolver,
        load_transcript_segments,
    )

    names: dict[str, str] = {}
    refs: dict[str, dict[str, Any]] = {}
    res = resolver or ManagedTranscriptResolver()
    for item in list_profiles(root=root):
        if item.status != "active":
            continue
        names[item.profile_id] = item.display_name
        texts: list[str] = []
        for link in list_profile_links(item.profile_id, root=root):
            if getattr(link, "status", "confirmed") not in ("confirmed",):
                continue
            if (
                exclude_managed_id
                and link.managed_transcript_id == exclude_managed_id
            ):
                continue
            try:
                resolved = res.resolve(link.managed_transcript_id)
                segs = load_transcript_segments(resolved.transcript_path)
            except Exception:
                continue
            texts.extend(texts_for_speaker(segs, link.local_speaker_key))
        vector = build_style_vector(texts)
        if vector is not None:
            refs[item.profile_id] = vector
    return refs, names


def rank_style_open_set(
    query: Mapping[str, Any],
    refs: Mapping[str, Mapping[str, Any]],
    *,
    names: Mapping[str, str] | None = None,
) -> ChannelCandidate | None:
    """Open-set rank vs profile style refs; abstain unless unique strong winner."""
    scored: list[tuple[str, float]] = []
    for profile_id, ref in refs.items():
        scored.append((profile_id, style_similarity(query, ref)))
    scored.sort(key=lambda item: (-item[1], item[0]))
    if not scored:
        return None
    best_id, best = scored[0]
    if best < STYLE_STRONG_MIN:
        return None
    if len(scored) > 1 and (best - scored[1][1]) < STYLE_MARGIN:
        return None
    display = (names or {}).get(best_id) or best_id
    return ChannelCandidate(
        channel="style",
        display_name=display,
        profile_id=best_id,
        score=best,
        confidence="strong",
        evidence={"score": best, "runner_up": scored[1][1] if len(scored) > 1 else None},
    )
