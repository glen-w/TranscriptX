"""Optional YAKE / KeyBERT methods with failure isolation (imports stay here)."""

from __future__ import annotations

from typing import Any

from transcriptx.core.analysis.keyphrases.contract import (
    MethodRankBlock,
    RankedPhrase,
    SkippedMethod,
)
from transcriptx.core.analysis.keyphrases.scoring import assign_ranks_and_weights


def _segment_texts(filtered_segments: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for seg in filtered_segments:
        if not isinstance(seg, dict):
            continue
        text = str(seg.get("content_text") or seg.get("text") or "").strip()
        if text:
            texts.append(text)
    return texts


def run_yake(
    filtered_segments: list[dict[str, Any]],
    *,
    max_phrases: int,
    lan: str,
    n: int,
    top: int,
    window_size: int,
) -> tuple[MethodRankBlock | None, SkippedMethod | None]:
    try:
        import yake  # type: ignore
    except Exception as exc:
        return None, SkippedMethod(
            method="yake",
            reason_code="missing_package",
            detail=str(exc)[:200],
        )
    texts = _segment_texts(filtered_segments)
    if not texts:
        return None, SkippedMethod(method="yake", reason_code="empty_result")
    try:
        extractor = yake.KeywordExtractor(
            lan=lan, n=n, top=max(top, max_phrases), windowsSize=window_size
        )
        # Join with paragraph breaks; YAKE scores whole doc — still per-method only.
        joined = "\n\n".join(texts)
        raw = extractor.extract_keywords(joined) or []
    except Exception as exc:
        return None, SkippedMethod(
            method="yake",
            reason_code="inference_failure",
            detail=str(exc)[:200],
        )
    phrases: list[RankedPhrase] = []
    for phrase, score in raw[:max_phrases]:
        key = " ".join(str(phrase).casefold().split())
        if not key:
            continue
        phrases.append(
            RankedPhrase(
                phrase=str(phrase),
                canonical_key=key,
                token_count=len(key.split()),
                rank=1,
                raw_score=float(score),
                score_direction="lower_is_better",
                rank_weight=0.0,
                occurrence_count=1,
                segment_support=1,
                evidence=[],
            )
        )
    if not phrases:
        return None, SkippedMethod(method="yake", reason_code="empty_result")
    ranked = assign_ranks_and_weights(phrases)
    return (
        MethodRankBlock(method="yake", phrases=ranked, evaluation_state="scored"),
        None,
    )


def _keybert_model_available(model_id: str) -> bool:
    try:
        from transformers import AutoConfig

        AutoConfig.from_pretrained(model_id, local_files_only=True)
        return True
    except Exception:
        return False


def run_keybert(
    filtered_segments: list[dict[str, Any]],
    *,
    max_phrases: int,
    model_id: str,
) -> tuple[MethodRankBlock | None, SkippedMethod | None]:
    try:
        from keybert import KeyBERT  # type: ignore
    except Exception as exc:
        return None, SkippedMethod(
            method="keybert",
            reason_code="missing_package",
            detail=str(exc)[:200],
        )
    if not _keybert_model_available(model_id):
        return None, SkippedMethod(
            method="keybert",
            reason_code="model_unavailable",
            detail=f"local_files_only miss for {model_id}",
        )
    texts = _segment_texts(filtered_segments)
    if not texts:
        return None, SkippedMethod(method="keybert", reason_code="empty_result")
    # Prohibit implicit downloads via SentenceTransformer(local_files_only=True).
    try:
        from sentence_transformers import SentenceTransformer

        embedder = SentenceTransformer(model_id, local_files_only=True)
        kw_model = KeyBERT(model=embedder)
        joined = "\n\n".join(texts)
        raw = kw_model.extract_keywords(
            joined, keyphrase_ngram_range=(1, 3), top_n=max_phrases
        ) or []
    except OSError as exc:
        msg = str(exc).lower()
        if "out of memory" in msg or "cuda" in msg:
            try:
                from sentence_transformers import SentenceTransformer
                from keybert import KeyBERT as _KB

                embedder = SentenceTransformer(
                    model_id, local_files_only=True, device="cpu"
                )
                kw_model = _KB(model=embedder)
                joined = "\n\n".join(texts)
                raw = kw_model.extract_keywords(
                    joined, keyphrase_ngram_range=(1, 3), top_n=max_phrases
                ) or []
            except Exception as exc2:
                return None, SkippedMethod(
                    method="keybert",
                    reason_code="oom_or_device_fallback_exhausted",
                    detail=str(exc2)[:200],
                )
        else:
            return None, SkippedMethod(
                method="keybert",
                reason_code="inference_failure",
                detail=str(exc)[:200],
            )
    except Exception as exc:
        return None, SkippedMethod(
            method="keybert",
            reason_code="inference_failure",
            detail=str(exc)[:200],
        )
    phrases: list[RankedPhrase] = []
    for phrase, score in raw[:max_phrases]:
        key = " ".join(str(phrase).casefold().split())
        if not key:
            continue
        phrases.append(
            RankedPhrase(
                phrase=str(phrase),
                canonical_key=key,
                token_count=len(key.split()),
                rank=1,
                raw_score=float(score),
                score_direction="higher_is_better",
                rank_weight=0.0,
                occurrence_count=1,
                segment_support=1,
                evidence=[],
            )
        )
    if not phrases:
        return None, SkippedMethod(method="keybert", reason_code="empty_result")
    ranked = assign_ranks_and_weights(phrases)
    return (
        MethodRankBlock(method="keybert", phrases=ranked, evaluation_state="scored"),
        None,
    )
