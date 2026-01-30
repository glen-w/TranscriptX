"""
Pure metrics for affect_tension: entropy, mismatch rules, trust_like, volatility, derived indices.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

# GoEmotions / NRC labels that count as "positive emotion" for mismatch
POSITIVE_EMOTION_LABELS = frozenset(
    {
        "joy",
        "excitement",
        "approval",
        "gratitude",
        "love",
        "optimism",
        "relief",
        "amusement",
        "caring",
        "pride",
        "admiration",
        "desire",
        "positive",
    }
)

# Labels that contribute to "trust-like" when trust is missing
TRUST_LIKE_LABELS = {"approval", "gratitude", "admiration", "optimism"}
TRUST_LIKE_WEIGHTS = {"approval": 0.3, "gratitude": 0.3, "admiration": 0.2, "optimism": 0.2}


def emotion_entropy(scores: Dict[str, float]) -> Optional[float]:
    """
    Entropy of emotion distribution (scores sum to 1 or are raw scores).
    Returns None if no distribution.
    """
    if not scores:
        return None
    total = sum(scores.values())
    if total <= 0:
        return None
    entropy = 0.0
    for v in scores.values():
        p = v / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def trust_like_score(scores: Dict[str, float]) -> Optional[float]:
    """
    If 'trust' in scores, return it. Else return weighted sum of
    approval, gratitude, admiration, optimism if any present.
    """
    if not scores:
        return None
    label_lower = {k.lower(): v for k, v in scores.items()}
    if "trust" in label_lower:
        return label_lower["trust"]
    total = 0.0
    weight_sum = 0.0
    for label, w in TRUST_LIKE_WEIGHTS.items():
        if label in label_lower:
            total += w * label_lower[label]
            weight_sum += w
    if weight_sum <= 0:
        return None
    return total / weight_sum if weight_sum else None


def is_positive_emotion(scores: Dict[str, float], threshold: float) -> bool:
    """True if any positive-emotion label has score >= threshold."""
    if not scores or threshold <= 0:
        return False
    label_lower = {k.lower(): v for k, v in scores.items()}
    for label in POSITIVE_EMOTION_LABELS:
        if label in label_lower and label_lower[label] >= threshold:
            return True
    return False


def affect_mismatch_posneg(
    sentiment_compound_norm: float,
    emotion_scores: Dict[str, float],
    pos_emotion_threshold: float,
    mismatch_compound_threshold: float,
) -> bool:
    """
    True when positive emotion (from emotion_scores) + negative sentiment
    (compound <= mismatch_compound_threshold).
    """
    neg_sentiment = sentiment_compound_norm <= mismatch_compound_threshold
    pos_emotion = is_positive_emotion(emotion_scores, pos_emotion_threshold)
    return bool(pos_emotion and neg_sentiment)


def affect_trust_neutral(
    sentiment_compound_norm: float,
    trust_like: Optional[float],
    trust_like_threshold: float,
    neutral_band: float = 0.1,
) -> Optional[bool]:
    """
    True when neutral sentiment (|compound| <= neutral_band) and high trust-like.
    None if trust_like is None.
    """
    if trust_like is None:
        return None
    neutral = abs(sentiment_compound_norm) <= neutral_band
    high_trust = trust_like >= trust_like_threshold
    return neutral and high_trust


def emotion_volatility_proxy(
    segment_index: int,
    primary_labels: List[str],
    window: int = 3,
) -> float:
    """
    Proxy for volatility: fraction of preceding `window` segments with
    different primary emotion label (0 = no change, 1 = all different).
    """
    if window <= 0 or segment_index <= 0 or not primary_labels:
        return 0.0
    current = primary_labels[segment_index] if segment_index < len(primary_labels) else ""
    start = max(0, segment_index - window)
    count = 0
    diff = 0
    for i in range(start, segment_index):
        if i < len(primary_labels):
            count += 1
            if primary_labels[i] != current:
                diff += 1
    if count == 0:
        return 0.0
    return diff / count


def compute_derived_indices(
    segments: List[Dict[str, Any]],
    speaker_segment_indexes: Dict[str, List[int]],
    thresholds: Dict[str, float],
    weights: Dict[str, float],
) -> Dict[str, Any]:
    """
    Compute polite_tension_index, suppressed_conflict_score, institutional_tone_affect_delta
    per speaker and global. Uses thresholds and weights from config.
    """
    mismatch_compound = thresholds.get("mismatch_compound_threshold", -0.1)
    trust_like_th = thresholds.get("trust_like_threshold", 0.3)
    pos_emotion_th = thresholds.get("pos_emotion_threshold", 0.3)
    w_posneg = weights.get("weight_posneg_mismatch", 0.4)
    w_trust = weights.get("weight_trust_neutral", 0.3)
    w_entropy = weights.get("weight_entropy", 0.15)
    w_vol = weights.get("weight_volatility", 0.15)

    primary_labels = [
        seg.get("context_emotion_primary") or "" for seg in segments
    ]

    def segment_scores(inds: List[int]) -> Dict[str, float]:
        polite = 0.0
        suppressed = 0.0
        delta_sum = 0.0
        n = 0
        for i in inds:
            if i >= len(segments):
                continue
            seg = segments[i]
            compound = seg.get("sentiment_compound_norm")
            if compound is None:
                compound = seg.get("sentiment", {}).get("compound", 0.0)
            scores = seg.get("context_emotion_scores") or {}
            trust = trust_like_score(scores)
            mismatch = affect_mismatch_posneg(
                compound, scores, pos_emotion_th, mismatch_compound
            )
            trust_neutral = affect_trust_neutral(
                compound, trust, trust_like_th
            )
            ent = emotion_entropy(scores)
            vol = emotion_volatility_proxy(i, primary_labels, 5)
            # Polite tension: mismatch or trust_neutral
            if mismatch:
                polite += w_posneg
            if trust_neutral:
                polite += w_trust
            if ent is not None:
                polite += w_entropy * min(ent / 4.0, 1.0)  # cap entropy contribution
            polite += w_vol * vol
            suppressed += 1.0 if mismatch else 0.0
            suppressed += 0.5 if trust_neutral else 0.0
            # Tone–affect delta: |compound| vs dominant emotion polarity
            pos_emo = is_positive_emotion(scores, pos_emotion_th)
            if pos_emo and compound < 0:
                delta_sum += abs(compound)
            elif not pos_emo and compound > 0:
                delta_sum += compound
            n += 1
        count = max(n, 1)
        return {
            "polite_tension_index": polite / count,
            "suppressed_conflict_score": suppressed / count,
            "institutional_tone_affect_delta": delta_sum / count,
        }

    all_inds = list(range(len(segments)))
    global_scores = segment_scores(all_inds)
    by_speaker: Dict[str, Dict[str, float]] = {}
    for speaker, inds in speaker_segment_indexes.items():
        if inds:
            by_speaker[speaker] = segment_scores(inds)

    return {
        "global": global_scores,
        "by_speaker": by_speaker,
    }
