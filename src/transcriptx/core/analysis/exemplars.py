"""Speaker exemplar scoring utilities (core, no UI imports)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional
import math
import re
import time

from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]

# SpeakerExemplarsConfig is defined in the config layer, but some environments
# can end up with stale/partial imports during rapid refactors or editable installs.
# Make this import robust so the web UI can still start.
try:
    from transcriptx.core.utils.config.analysis import (  # type: ignore[import-untyped]
        SpeakerExemplarsConfig,
    )
except Exception:  # pragma: no cover
    try:
        from transcriptx.core.utils.config import (  # type: ignore[import-untyped]
            SpeakerExemplarsConfig,
        )
    except Exception:

        @dataclass
        class SpeakerExemplarsConfig:  # type: ignore[no-redef]
            """Fallback config for speaker exemplars (bootstrapping only)."""

            enabled: bool = True
            count: int = 10
            min_words: int = 3
            max_words: int = 80
            max_segments_considered: int = 2000
            merge_adjacent: bool = True

            dedupe: bool = True
            near_dedupe: bool = False
            near_dedupe_threshold: float = 0.85
            near_dedupe_max_checks: int = 200

            methods_enabled: dict[str, bool] = field(
                default_factory=lambda: {
                    "unique": True,
                    "tfidf_within_speaker": True,
                    "distinctive_vs_others": True,
                }
            )
            weights: dict[str, float] = field(
                default_factory=lambda: {
                    "unique": 0.34,
                    "tfidf_within_speaker": 0.33,
                    "distinctive_vs_others": 0.33,
                }
            )

            distinctive_scope: str = "transcript"
            distinctive_min_other_segments: int = 50
            distinctive_max_other_speakers: int = 6
            distinctive_max_other_segments_total: int = 2000
            distinctive_max_other_segments_per_speaker: int = 400

            tfidf_max_features: int = 1000
            tfidf_ngram_range: tuple[int, int] = (1, 2)

            length_prior_enabled: bool = True
            length_prior_center: float = 18.0
            length_prior_sigma: float = 12.0


TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
PUNCTUATION_BOUNDARY = (".", "?", "!", "…", ":", ";")


@dataclass(frozen=True)
class SegmentRecord:
    segment_id: object
    segment_index: int
    speaker_id: str
    text: str
    word_count: Optional[int] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass(frozen=True)
class ExemplarItem:
    segment_id: object
    segment_index: int
    speaker_id: str
    text: str
    word_count: int
    start_time: Optional[float]
    end_time: Optional[float]
    combined_score: float
    method_scores: dict[str, float]


@dataclass(frozen=True)
class ExemplarResults:
    combined: list[ExemplarItem]
    per_method: dict[str, list[ExemplarItem]]
    metadata: dict[str, object]


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9']+", " ", text.lower())
    return " ".join(cleaned.split())


def _word_count(text: str) -> int:
    return len(text.split())


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((pct / 100.0) * (len(ordered) - 1)))
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def _length_prior(word_count: int, center: float, sigma: float) -> float:
    if sigma <= 0:
        return 1.0
    z = (word_count - center) / sigma
    return math.exp(-0.5 * (z * z))


def _merge_adjacent(
    segments: list[SegmentRecord], config: SpeakerExemplarsConfig
) -> list[SegmentRecord]:
    if not segments or not config.merge_adjacent:
        return segments

    merged: list[SegmentRecord] = []
    current = segments[0]
    current_text = current.text.strip()
    current_words = current.word_count or _word_count(current_text)
    current_start = current.start_time
    current_end = current.end_time

    def _ends_with_boundary(text: str) -> bool:
        stripped = text.rstrip()
        return bool(stripped) and stripped.endswith(PUNCTUATION_BOUNDARY)

    for segment in segments[1:]:
        next_text = segment.text.strip()
        if (
            segment.speaker_id == current.speaker_id
            and segment.segment_index == current.segment_index + 1
            and not _ends_with_boundary(current_text)
        ):
            next_words = segment.word_count or _word_count(next_text)
            if current_words + next_words <= config.max_words:
                current_text = f"{current_text} {next_text}".strip()
                current_words += next_words
                current_end = segment.end_time
                current = SegmentRecord(
                    segment_id=current.segment_id,
                    segment_index=current.segment_index,
                    speaker_id=current.speaker_id,
                    text=current_text,
                    word_count=current_words,
                    start_time=current_start,
                    end_time=current_end,
                )
                continue

        merged.append(current)
        current = segment
        current_text = current.text.strip()
        current_words = current.word_count or _word_count(current_text)
        current_start = current.start_time
        current_end = current.end_time

    merged.append(current)
    return merged


def _dedupe_segments(
    segments: list[SegmentRecord], config: SpeakerExemplarsConfig
) -> list[SegmentRecord]:
    if not segments or not config.dedupe:
        return segments

    seen = set()
    deduped: list[SegmentRecord] = []
    for segment in segments:
        key = _normalize_text(segment.text)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(segment)

    if not config.near_dedupe:
        return deduped

    accepted: list[SegmentRecord] = []
    accepted_tokens: list[set[str]] = []
    for segment in deduped:
        tokens = set(_tokenize(segment.text))
        if not tokens:
            continue
        is_dup = False
        checks = 0
        for existing in accepted_tokens:
            checks += 1
            if checks > config.near_dedupe_max_checks:
                break
            union = tokens | existing
            if not union:
                continue
            score = len(tokens & existing) / len(union)
            if score >= config.near_dedupe_threshold:
                is_dup = True
                break
        if not is_dup:
            accepted.append(segment)
            accepted_tokens.append(tokens)

    return accepted


def _rank_normalize(
    segments: list[SegmentRecord], scores: list[float]
) -> Optional[list[float]]:
    if len(scores) < 5:
        return None
    indexed = list(enumerate(scores))
    indexed.sort(
        key=lambda item: (
            -item[1],
            segments[item[0]].segment_index,
            str(segments[item[0]].segment_id),
        )
    )
    n = len(scores)
    if n <= 1:
        return None
    normalized = [0.0] * n
    for rank, (idx, _) in enumerate(indexed):
        normalized[idx] = 1.0 - (rank / (n - 1))
    return normalized


def _apply_length_prior(
    segments: list[SegmentRecord], scores: list[float], config: SpeakerExemplarsConfig
) -> list[float]:
    if not config.length_prior_enabled:
        return scores
    weighted = []
    for segment, score in zip(segments, scores):
        wc = segment.word_count or _word_count(segment.text)
        weight = _length_prior(
            wc, config.length_prior_center, config.length_prior_sigma
        )
        weighted.append(score * weight)
    return weighted


def _compute_unique_scores(
    segments: list[SegmentRecord], config: SpeakerExemplarsConfig
) -> list[float]:
    token_lists = [_tokenize(seg.text) for seg in segments]
    all_tokens = [t for tokens in token_lists for t in tokens]
    if not all_tokens:
        return [0.0] * len(segments)

    counts: dict[str, int] = {}
    for token in all_tokens:
        counts[token] = counts.get(token, 0) + 1
    total = len(all_tokens)
    vocab = len(counts)
    k = 1.0

    token_surprisals = [
        -math.log((counts[token] + k) / (total + k * vocab)) for token in all_tokens
    ]
    cap = _percentile(token_surprisals, 95.0)

    scores: list[float] = []
    for tokens in token_lists:
        if not tokens:
            scores.append(0.0)
            continue
        values = []
        for token in tokens:
            value = -math.log((counts.get(token, 0) + k) / (total + k * vocab))
            values.append(min(value, cap))
        surprisal = sum(values) / len(values)

        freq: dict[str, int] = {}
        for token in tokens:
            freq[token] = freq.get(token, 0) + 1
        repeat_ratio = max(freq.values()) / len(tokens)
        penalty = 1.0 - max(0.0, min(repeat_ratio, 0.6))
        scores.append(surprisal * penalty)

    return scores


def _compute_tfidf_scores(
    texts: list[str], max_features: int, ngram_range: tuple[int, int]
) -> list[float]:
    if not texts:
        return []
    vectorizer = TfidfVectorizer(max_features=max_features, ngram_range=ngram_range)
    matrix = vectorizer.fit_transform(texts)
    scores: list[float] = []
    for row in matrix:
        if row.nnz == 0:
            scores.append(0.0)
        else:
            scores.append(float(row.sum() / row.nnz))
    return scores


def compute_speaker_exemplars(
    segments: Iterable[SegmentRecord],
    other_segments: Optional[Iterable[SegmentRecord]],
    config: SpeakerExemplarsConfig,
) -> ExemplarResults:
    start = time.perf_counter()
    candidates = list(segments)
    other_segments = list(other_segments or [])
    other_count = len(other_segments)
    candidates.sort(key=lambda seg: seg.segment_index)
    input_count = len(candidates)

    filtered = []
    for segment in candidates:
        text = segment.text.strip()
        if not text:
            continue
        wc = segment.word_count or _word_count(text)
        if wc < config.min_words or wc > config.max_words:
            continue
        filtered.append(
            SegmentRecord(
                segment_id=segment.segment_id,
                segment_index=segment.segment_index,
                speaker_id=str(segment.speaker_id),
                text=text,
                word_count=wc,
                start_time=segment.start_time,
                end_time=segment.end_time,
            )
        )

    if (
        config.max_segments_considered
        and len(filtered) > config.max_segments_considered
    ):
        filtered = filtered[: config.max_segments_considered]

    merged = _merge_adjacent(filtered, config)
    deduped = _dedupe_segments(merged, config)

    method_raw: dict[str, Optional[list[float]]] = {}
    texts = [seg.text for seg in deduped]

    if config.methods_enabled.get("unique"):
        raw_unique = _compute_unique_scores(deduped, config)
        raw_unique = _apply_length_prior(deduped, raw_unique, config)
        method_raw["unique"] = raw_unique
    else:
        method_raw["unique"] = None

    if config.methods_enabled.get("tfidf_within_speaker"):
        raw_tfidf = _compute_tfidf_scores(
            texts, config.tfidf_max_features, config.tfidf_ngram_range
        )
        raw_tfidf = _apply_length_prior(deduped, raw_tfidf, config)
        method_raw["tfidf_within_speaker"] = raw_tfidf
    else:
        method_raw["tfidf_within_speaker"] = None

    if config.methods_enabled.get("distinctive_vs_others"):
        if other_count < config.distinctive_min_other_segments:
            method_raw["distinctive_vs_others"] = None
        else:
            other_texts = [seg.text for seg in other_segments]
            combined_texts = texts + other_texts
            raw = _compute_tfidf_scores(
                combined_texts,
                config.tfidf_max_features,
                config.tfidf_ngram_range,
            )
            speaker_raw = raw[: len(texts)]
            speaker_raw = _apply_length_prior(deduped, speaker_raw, config)
            method_raw["distinctive_vs_others"] = speaker_raw
    else:
        method_raw["distinctive_vs_others"] = None

    method_norm: dict[str, Optional[list[float]]] = {}
    for method_name, raw_scores in method_raw.items():
        if raw_scores is None:
            method_norm[method_name] = None
            continue
        normalized = _rank_normalize(deduped, raw_scores)
        method_norm[method_name] = normalized

    available = {
        name: scores for name, scores in method_norm.items() if scores is not None
    }
    weight_sum = sum(config.weights.get(name, 0.0) for name in available.keys())
    combined_scores = [0.0] * len(deduped)
    if available and weight_sum > 0:
        for method_name, method_scores in available.items():
            weight = config.weights.get(method_name, 0.0) / weight_sum
            for idx, value in enumerate(method_scores):
                combined_scores[idx] += value * weight

    combined_items: list[ExemplarItem] = []
    for idx, (segment, combined) in enumerate(zip(deduped, combined_scores)):
        scores_by_method = {
            method_name: (values[idx] if values is not None else 0.0)
            for method_name, values in method_norm.items()
        }
        combined_items.append(
            ExemplarItem(
                segment_id=segment.segment_id,
                segment_index=segment.segment_index,
                speaker_id=segment.speaker_id,
                text=segment.text,
                word_count=segment.word_count or _word_count(segment.text),
                start_time=segment.start_time,
                end_time=segment.end_time,
                combined_score=combined,
                method_scores=scores_by_method,
            )
        )

    combined_items.sort(
        key=lambda item: (
            -item.combined_score,
            item.segment_index,
            str(item.segment_id),
        )
    )
    combined_items = combined_items[: config.count]

    per_method: dict[str, list[ExemplarItem]] = {}
    for method_name, method_scores in method_norm.items():
        if method_scores is None:
            continue
        items: list[ExemplarItem] = []
        for segment, score in zip(deduped, method_scores):
            items.append(
                ExemplarItem(
                    segment_id=segment.segment_id,
                    segment_index=segment.segment_index,
                    speaker_id=segment.speaker_id,
                    text=segment.text,
                    word_count=segment.word_count or _word_count(segment.text),
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    combined_score=score,
                    method_scores={method_name: score},
                )
            )
        items.sort(
            key=lambda item: (
                -item.combined_score,
                item.segment_index,
                str(item.segment_id),
            )
        )
        per_method[method_name] = items[: config.count]

    duration = time.perf_counter() - start
    metadata = {
        "input_count": input_count,
        "filtered_count": len(filtered),
        "merged_count": len(merged),
        "deduped_count": len(deduped),
        "other_segments": other_count,
        "duration_seconds": round(duration, 4),
        "methods_available": list(available.keys()),
    }

    return ExemplarResults(
        combined=combined_items,
        per_method=per_method,
        metadata=metadata,
    )
