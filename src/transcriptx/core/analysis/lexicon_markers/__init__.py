"""Shared lexicon marker matching for Wave 2 linguistics modules."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ALGORITHM_VERSION = "lexicon_markers_v1"
TOKENIZER_VERSION = "unicode_word_v1"
ENGLISH_CODES = frozenset({"en", "eng", "en-us", "en-gb", "en_us", "en_gb"})

_TOKEN_RE = re.compile(r"[^\W\d_]+(?:['\u2019-][^\W\d_]+)*", re.UNICODE)
_PACKAGE_LEXICONS = "transcriptx.preprocessing.lexicons"


@dataclass(frozen=True)
class MarkerPhrase:
    surface: str
    category: str
    token_count: int


@dataclass(frozen=True)
class MarkerHit:
    speaker: str
    segment_index: int
    start: int
    end: int
    surface: str
    category: str
    module: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker,
            "segment_index": self.segment_index,
            "start": self.start,
            "end": self.end,
            "surface": self.surface,
            "category": self.category,
            "module": self.module,
        }


def normalize_language_code(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().lower().replace("_", "-")
    if not text:
        return None
    primary = text.split("-", 1)[0]
    return primary or None


def resolve_transcript_language(
    segments: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str | None, str]:
    """Return (normalized_code_or_None, resolution_tag)."""
    meta = metadata or {}
    meta_lang = normalize_language_code(
        meta.get("language") if isinstance(meta, Mapping) else None
    )
    seg_langs: list[str] = []
    for seg in segments:
        if not isinstance(seg, Mapping):
            continue
        code = normalize_language_code(seg.get("language"))
        if code:
            seg_langs.append(code)
    unique = sorted(set(seg_langs))
    if len(unique) > 1:
        if all(u in {"en", "eng"} or u.startswith("en") for u in unique):
            return "en", "mixed_english_variants"
        return unique[0], "mixed_segment_languages"
    if len(unique) == 1:
        return unique[0], "segment_language"
    if meta_lang:
        return meta_lang, "metadata_language"
    return "en", "assumed_en_missing_metadata"


def is_english_supported(code: str | None) -> bool:
    if code is None:
        return False
    normalized = normalize_language_code(code) or code
    if normalized in ENGLISH_CODES or normalized.startswith("en"):
        return True
    return False


def tokenize(text: str) -> list[str]:
    return [
        m.group(0).casefold()
        for m in _TOKEN_RE.finditer(text or "")
        if len(m.group(0)) >= 2
    ]


def count_tokens(text: str) -> int:
    return len(tokenize(text))


def _phrase_token_count(phrase: str) -> int:
    return max(1, len(tokenize(phrase)))


def load_categorized_lexicon(path: Path | str) -> dict[str, tuple[MarkerPhrase, ...]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    categories = raw.get("categories") or {}
    if not isinstance(categories, dict):
        raise ValueError(f"Invalid lexicon categories in {path}")
    out: dict[str, list[MarkerPhrase]] = {}
    for category, phrases in categories.items():
        if not isinstance(phrases, list):
            continue
        items: list[MarkerPhrase] = []
        for phrase in phrases:
            surface = str(phrase).strip()
            if not surface:
                continue
            items.append(
                MarkerPhrase(
                    surface=surface.casefold(),
                    category=str(category),
                    token_count=_phrase_token_count(surface),
                )
            )
        # Longest phrase first for greedy matching
        items.sort(key=lambda p: (-len(p.surface), p.surface))
        out[str(category)] = items
    return {k: tuple(v) for k, v in out.items()}


@lru_cache(maxsize=8)
def load_package_lexicon(filename: str) -> dict[str, tuple[MarkerPhrase, ...]]:
    root = resources.files(_PACKAGE_LEXICONS)
    data = root.joinpath(filename).read_text(encoding="utf-8")
    raw = json.loads(data)
    categories = raw.get("categories") or {}
    out: dict[str, list[MarkerPhrase]] = {}
    for category, phrases in categories.items():
        if not isinstance(phrases, list):
            continue
        items: list[MarkerPhrase] = []
        for phrase in phrases:
            surface = str(phrase).strip()
            if not surface:
                continue
            items.append(
                MarkerPhrase(
                    surface=surface.casefold(),
                    category=str(category),
                    token_count=_phrase_token_count(surface),
                )
            )
        items.sort(key=lambda p: (-len(p.surface), p.surface))
        out[str(category)] = items
    return {k: tuple(v) for k, v in out.items()}


def iter_phrases(
    lexicon: Mapping[str, Sequence[MarkerPhrase]],
    enabled_categories: Iterable[str] | None,
) -> list[MarkerPhrase]:
    enabled = (
        None if enabled_categories is None else {str(c) for c in enabled_categories}
    )
    phrases: list[MarkerPhrase] = []
    for category, items in lexicon.items():
        if enabled is not None and category not in enabled:
            continue
        phrases.extend(items)
    phrases.sort(key=lambda p: (-len(p.surface), p.surface))
    return phrases


def match_phrases_in_text(
    text: str,
    phrases: Sequence[MarkerPhrase],
    *,
    speaker: str,
    segment_index: int,
    module: str,
) -> list[MarkerHit]:
    """Greedy non-overlapping longest-match-first over casefolded text."""
    if not text or not phrases:
        return []
    lower = text.casefold()
    occupied = [False] * len(lower)
    hits: list[MarkerHit] = []

    # Collect candidate matches then resolve overlaps by start then length
    candidates: list[tuple[int, int, MarkerPhrase]] = []
    for phrase in phrases:
        needle = phrase.surface
        if not needle:
            continue
        start = 0
        while True:
            idx = lower.find(needle, start)
            if idx < 0:
                break
            end = idx + len(needle)
            # Prefer word-ish boundaries for single-token phrases
            if _has_alnum_neighbor(lower, idx, end):
                start = idx + 1
                continue
            candidates.append((idx, end, phrase))
            start = idx + 1

    candidates.sort(key=lambda c: (c[0], -(c[1] - c[0])))
    for start, end, phrase in candidates:
        if any(occupied[start:end]):
            continue
        for i in range(start, end):
            occupied[i] = True
        hits.append(
            MarkerHit(
                speaker=speaker,
                segment_index=segment_index,
                start=start,
                end=end,
                surface=text[start:end],
                category=phrase.category,
                module=module,
            )
        )
    hits.sort(key=lambda h: (h.segment_index, h.start, h.end))
    return hits


def _has_alnum_neighbor(text: str, start: int, end: int) -> bool:
    left_ok = start == 0 or not text[start - 1].isalnum()
    right_ok = end >= len(text) or not text[end].isalnum()
    return not (left_ok and right_ok)


def aggregate_rates(
    hits: Sequence[MarkerHit],
    token_counts_by_speaker: Mapping[str, int],
    categories: Sequence[str],
    *,
    min_tokens_for_rates: int,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Build global_stats and speaker_stats with counts and rates."""
    category_list = list(categories)

    def _empty_counts() -> dict[str, int]:
        return {c: 0 for c in category_list}

    speaker_counts: dict[str, dict[str, int]] = {
        speaker: _empty_counts() for speaker in token_counts_by_speaker
    }
    global_counts = _empty_counts()
    for hit in hits:
        if hit.category not in global_counts:
            continue
        global_counts[hit.category] += 1
        if hit.speaker not in speaker_counts:
            speaker_counts[hit.speaker] = _empty_counts()
        speaker_counts[hit.speaker][hit.category] += 1

    global_tokens = sum(int(v) for v in token_counts_by_speaker.values())
    global_stats = _stats_for_scope(
        global_counts, global_tokens, category_list, min_tokens_for_rates
    )
    speaker_stats = {
        speaker: _stats_for_scope(
            counts,
            int(token_counts_by_speaker.get(speaker, 0)),
            category_list,
            min_tokens_for_rates,
        )
        for speaker, counts in speaker_counts.items()
    }
    return global_stats, speaker_stats


def _stats_for_scope(
    category_counts: Mapping[str, int],
    token_count: int,
    categories: Sequence[str],
    min_tokens_for_rates: int,
) -> dict[str, Any]:
    total_hits = sum(int(category_counts.get(c, 0)) for c in categories)
    rates: dict[str, float | None] = {}
    can_rate = token_count >= min_tokens_for_rates and token_count > 0
    for category in categories:
        count = int(category_counts.get(category, 0))
        rates[category] = (count * 100.0 / token_count) if can_rate else None
    return {
        "token_count": int(token_count),
        "total_marker_hits": int(total_hits),
        "category_counts": {c: int(category_counts.get(c, 0)) for c in categories},
        "hits_per_100_tokens": (
            (total_hits * 100.0 / token_count) if can_rate else None
        ),
        "category_rates_per_100_tokens": rates,
    }


def derive_epistemic_shares(global_stats: Mapping[str, Any]) -> dict[str, float | None]:
    counts = global_stats.get("category_counts") or {}
    if not isinstance(counts, Mapping):
        return {"hedge_share": None, "booster_share": None}
    hedges = (
        int(counts.get("epistemic_hedge", 0))
        + int(counts.get("approximator", 0))
        + int(counts.get("modal_uncertainty", 0))
    )
    boosters = int(counts.get("certainty_booster", 0))
    total = hedges + boosters
    if total <= 0:
        return {"hedge_share": None, "booster_share": None}
    return {
        "hedge_share": hedges / total,
        "booster_share": boosters / total,
    }


def derive_soft_request_ratio(global_stats: Mapping[str, Any]) -> float | None:
    counts = global_stats.get("category_counts") or {}
    if not isinstance(counts, Mapping):
        return None
    softeners = int(counts.get("request_softener", 0))
    bare = int(counts.get("bare_directive", 0))
    denom = softeners + bare
    if denom <= 0:
        return None
    return softeners / denom
