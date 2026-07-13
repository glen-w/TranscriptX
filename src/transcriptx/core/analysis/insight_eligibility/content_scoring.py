"""Deterministic scoring for candidate content phrases."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from transcriptx.core.analysis.phrase_quality.types import (
    BORDERLINE_STOPWORD_RATIO,
    LIGHT_VERB_HEAD,
    LOW_CONTENT_RATIO,
    LOW_DISTINCTIVENESS,
    WEAK_BARE_NOUN,
)

# Soft-penalty coefficients applied to content-phrase totals.
_CONTENT_PENALTY_COEFFS = {
    WEAK_BARE_NOUN: 0.20,
    LOW_CONTENT_RATIO: 0.15,
    LOW_DISTINCTIVENESS: 0.10,
    BORDERLINE_STOPWORD_RATIO: 0.10,
    LIGHT_VERB_HEAD: 0.05,
}


def score_content_phrases(
    phrases: List[str] | List[Dict[str, Any]],
    *,
    windows: List[Dict[str, Any]],
    speaker_blocks: List[Dict[str, Any]],
    entities: List[str] | None = None,
) -> Dict[str, Dict[str, float]]:
    counts: Dict[str, int] = defaultdict(int)
    window_hits: Dict[str, int] = defaultdict(int)
    block_hits: Dict[str, int] = defaultdict(int)
    quality_rows: Dict[str, List[Tuple[float, float, float]]] = defaultdict(list)
    penalty_rows: Dict[str, List[str]] = defaultdict(list)
    entity_set = {e.lower() for e in (entities or [])}

    for row in phrases:
        if isinstance(row, dict):
            phrase = str(row.get("phrase") or "").strip()
            quality = row.get("quality") or {}
            stopword_ratio = float(quality.get("stopword_ratio", 0.0) or 0.0)
            content_token_ratio = float(quality.get("content_token_ratio", 1.0) or 1.0)
            pos_weight = float(quality.get("pos_weight", 1.0) or 1.0)
            quality_rows[phrase].append(
                (stopword_ratio, content_token_ratio, pos_weight)
            )
            for code in quality.get("penalties") or []:
                penalty_rows[phrase].append(str(code))
        else:
            phrase = str(row).strip()
        if not phrase:
            continue
        counts[phrase] += 1

    for window in windows:
        text = str(window.get("text", "")).lower()
        for phrase in counts:
            if phrase in text:
                window_hits[phrase] += 1

    for block in speaker_blocks:
        text = str(block.get("text", "")).lower()
        for phrase in counts:
            if phrase in text:
                block_hits[phrase] += 1

    total_windows = max(1, len(windows))
    total_blocks = max(1, len(speaker_blocks))
    max_count = max(counts.values(), default=1)
    scores: Dict[str, Dict[str, float]] = {}
    for phrase, count in counts.items():
        frequency = float(count) / float(max_count)
        spread = float(window_hits.get(phrase, 0)) / float(total_windows)
        recurrence = float(block_hits.get(phrase, 0)) / float(total_blocks)
        entity_linkage = 1.0 if phrase in entity_set else 0.0
        base_total = (
            0.4 * frequency + 0.3 * spread + 0.2 * recurrence + 0.1 * entity_linkage
        )

        quality = quality_rows.get(phrase) or []
        if quality:
            qn = float(len(quality))
            stopword_ratio = sum(q[0] for q in quality) / qn
            content_token_ratio = sum(q[1] for q in quality) / qn
            pos_weight = sum(q[2] for q in quality) / qn
        else:
            stopword_ratio = 0.0
            content_token_ratio = 1.0
            pos_weight = 1.0

        raw_gravity = (
            0.4 * (1.0 - stopword_ratio) + 0.4 * content_token_ratio + 0.2 * pos_weight
        )
        semantic_gravity = min(1.2, max(0.6, 0.6 + (0.6 * raw_gravity)))
        total = base_total * semantic_gravity

        penalty_codes = set(penalty_rows.get(phrase) or [])
        soft_penalty = sum(
            _CONTENT_PENALTY_COEFFS.get(code, 0.0) for code in penalty_codes
        )
        # Do not also add policy rank_penalty here — it already encodes the same codes.
        total = max(0.0, total - soft_penalty)

        scores[phrase] = {
            "frequency": frequency,
            "spread": spread,
            "recurrence": recurrence,
            "entity_linkage": entity_linkage,
            "base_total": base_total,
            "semantic_gravity": semantic_gravity,
            "stopword_ratio": stopword_ratio,
            "content_token_ratio": content_token_ratio,
            "pos_weight": pos_weight,
            "soft_penalty": soft_penalty,
            "total": total,
        }

    return dict(
        sorted(
            scores.items(),
            key=lambda item: (-item[1]["total"], item[0]),
        )
    )
