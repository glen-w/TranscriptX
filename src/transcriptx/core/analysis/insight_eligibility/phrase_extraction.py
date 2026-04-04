"""Phrase extraction with phrase-level tic/discourse rejection."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Sequence, Set, Tuple

from transcriptx.core.utils.nlp_runtime import get_nlp_model
from transcriptx.core.utils.nlp_utils import DISCOURSE_HEDGE_TERMS, get_all_stopwords

from .content_filter import FilteredSegment
from .content_scoring import score_content_phrases


def _tokenize_text(text: str) -> List[Tuple[str, str]]:
    nlp = get_nlp_model()
    doc = nlp(text.lower())
    return [
        (token.text.lower(), token.pos_)
        for token in doc
        if token.is_alpha and token.text.strip()
    ]


def _is_single_char_alpha(token: str) -> bool:
    return len(token) == 1 and token.isalpha()


def _head_index(tokens_with_pos: Sequence[Tuple[str, str]]) -> int:
    # Prefer semantic anchors. Keep non-AUX verbs to retain verb-led insights.
    for idx, (_, pos) in enumerate(tokens_with_pos):
        if pos in {"NOUN", "PROPN"}:
            return idx
    for idx, (_, pos) in enumerate(tokens_with_pos):
        if pos == "VERB":
            return idx
    return 0


def _is_meaningful_token(token: str, pos: str, tic_mask: Set[str]) -> bool:
    if not token or not token.isalpha():
        return False
    if _is_single_char_alpha(token):
        return False
    if token in tic_mask:
        return False
    if token in DISCOURSE_HEDGE_TERMS:
        return False
    if pos in {"PRON", "DET", "ADP", "CCONJ", "SCONJ", "PART", "INTJ"}:
        return False
    if token in get_all_stopwords() and pos not in {"NOUN", "PROPN", "VERB"}:
        return False
    return True


def _phrase_quality(tokens_with_pos: Sequence[Tuple[str, str]]) -> Dict[str, float]:
    stopword_count = sum(
        1 for token, _ in tokens_with_pos if token in get_all_stopwords()
    )
    meaningful_count = sum(
        1
        for token, pos in tokens_with_pos
        if token not in get_all_stopwords() and pos in {"NOUN", "PROPN", "VERB"}
    )
    token_count = max(1, len(tokens_with_pos))
    head_pos = tokens_with_pos[_head_index(tokens_with_pos)][1]
    if head_pos in {"NOUN", "PROPN"}:
        pos_weight = 1.0
    elif head_pos == "VERB":
        pos_weight = 0.9
    else:
        pos_weight = 0.7
    return {
        "stopword_ratio": float(stopword_count) / float(token_count),
        "content_token_ratio": float(meaningful_count) / float(token_count),
        "pos_weight": pos_weight,
    }


def _has_low_information_structure(
    tokens_with_pos: Sequence[Tuple[str, str]],
    tic_mask: Set[str],
) -> bool:
    tokens = [token for token, _ in tokens_with_pos]
    if any(_is_single_char_alpha(token) for token in tokens):
        return True
    phrase = " ".join(tokens).strip()
    if not phrase:
        return True
    if phrase in tic_mask:
        return True
    if any(token in tic_mask for token in tokens):
        return True
    if any(token in DISCOURSE_HEDGE_TERMS for token in tokens):
        return True
    if all(token in get_all_stopwords() for token in tokens):
        return True
    if (
        len(tokens) == 1
        and len(tokens[0]) <= 2
        and tokens[0] not in {"ai", "ml", "ui", "ux"}
    ):
        return True
    if len(tokens) > 1 and all(len(token) <= 2 for token in tokens):
        return True
    if all(
        pos in {"PRON", "DET", "ADP", "CCONJ", "SCONJ", "PART", "INTJ"}
        for _, pos in tokens_with_pos
    ):
        return True
    return False


def _passes_phrase_quality_gate(
    tokens_with_pos: Sequence[Tuple[str, str]],
    tic_mask: Set[str],
    *,
    stopword_ratio_threshold: float = 0.6,
) -> bool:
    if not tokens_with_pos:
        return False

    # 1) Phrase has at least one meaningful token.
    meaningful_count = sum(
        1
        for token, pos in tokens_with_pos
        if _is_meaningful_token(token, pos, tic_mask)
    )
    if meaningful_count <= 0:
        return False

    # 2) Head token is content-bearing.
    hidx = _head_index(tokens_with_pos)
    head_token, head_pos = tokens_with_pos[hidx]
    if head_token in tic_mask:
        return False
    if head_token in get_all_stopwords() and head_pos not in {"NOUN", "PROPN", "VERB"}:
        return False
    if head_pos not in {"NOUN", "PROPN", "VERB"}:
        return False

    # 3) Stopword ratio is acceptable.
    stopword_count = sum(
        1 for token, _ in tokens_with_pos if token in get_all_stopwords()
    )
    stopword_ratio = float(stopword_count) / float(len(tokens_with_pos))
    if stopword_ratio > stopword_ratio_threshold:
        return False

    # 4) Phrase is not a known low-information pattern.
    if _has_low_information_structure(tokens_with_pos, tic_mask):
        return False
    return True


def _extract_noun_chunks(
    segments: List[FilteredSegment], tic_mask: Set[str]
) -> List[Dict[str, Any]]:
    nlp = get_nlp_model()
    phrases: List[Dict[str, Any]] = []
    for segment in segments:
        doc = nlp(segment.raw_text.lower())
        try:
            chunks = list(doc.noun_chunks)
        except Exception:
            chunks = []
        for chunk in chunks:
            phrase_tokens: List[Tuple[str, str]] = [
                (token.lemma_.lower(), token.pos_)
                for token in chunk
                if token.is_alpha and token.lemma_.strip()
            ]
            if not _passes_phrase_quality_gate(phrase_tokens, tic_mask):
                continue
            phrase = " ".join(token for token, _ in phrase_tokens).strip()
            if phrase:
                phrases.append(
                    {"phrase": phrase, "quality": _phrase_quality(phrase_tokens)}
                )
    return phrases


def _extract_ngrams(
    segments: List[FilteredSegment],
    tic_mask: Set[str],
    *,
    min_frequency: int = 2,
) -> List[Dict[str, Any]]:
    counter: Counter[str] = Counter()
    quality_map: Dict[str, Dict[str, float]] = {}
    for segment in segments:
        tokens = _tokenize_text(segment.raw_text)
        for n in (2, 3):
            for i in range(0, max(0, len(tokens) - n + 1)):
                ngram_tokens = tokens[i : i + n]
                if not _passes_phrase_quality_gate(ngram_tokens, tic_mask):
                    continue
                phrase = " ".join(token for token, _ in ngram_tokens).strip()
                if phrase:
                    counter[phrase] += 1
                    if phrase not in quality_map:
                        quality_map[phrase] = _phrase_quality(ngram_tokens)
    phrases = [
        {"phrase": phrase, "quality": quality_map.get(phrase, {})}
        for phrase, freq in counter.items()
        if freq >= min_frequency
    ]
    phrases.sort(key=lambda row: str(row.get("phrase") or ""))
    return phrases


def extract_content_phrases(
    segments: List[FilteredSegment],
    *,
    tic_mask: Set[str],
    windows: List[Dict[str, Any]],
    speaker_blocks: List[Dict[str, Any]],
    entities: List[str] | None = None,
    min_frequency: int = 2,
    min_score: float = 0.2,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, float]]]:
    noun_chunks = _extract_noun_chunks(segments, tic_mask)
    ngrams = _extract_ngrams(segments, tic_mask, min_frequency=min_frequency)
    phrase_candidates = noun_chunks + ngrams
    if not phrase_candidates:
        return [], {}

    scores = score_content_phrases(
        phrase_candidates,
        windows=windows,
        speaker_blocks=speaker_blocks,
        entities=entities,
    )

    rows: List[Dict[str, Any]] = []
    for phrase, metrics in scores.items():
        if metrics["total"] < min_score:
            continue
        rows.append({"phrase": phrase, "score": metrics})

    rows.sort(key=lambda row: (-row["score"]["total"], row["phrase"]))
    return rows, scores
