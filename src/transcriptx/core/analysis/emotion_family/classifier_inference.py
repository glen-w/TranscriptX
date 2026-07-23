"""Classifier inference cache + batch scoring for emotion-family producers.

Internal submodule — import directly; not part of ``emotion_family.__all__``.

Operates only after a classifier has loaded successfully. Does not instantiate
cache stores, derive roots, recompute inference keys, load models, know module
IDs, build compat/fingerprints/runtime metadata, select RunStatus, clear
projections, or build producer ``_failed`` result dicts.

Logging: only non-fatal inference-cache *write* failures. ``score_texts_fn``
exceptions are returned as ``ClassifierInferenceFailure`` without helper
logging so producers retain their own warning behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Iterable,
    Literal,
    Mapping,
    Sequence,
)

from transcriptx.core.analysis.emotion_family.cache_validation import (
    validate_classifier_cache_row,
)
from transcriptx.core.analysis.emotion_family.language import is_english
from transcriptx.core.analysis.emotion_family.split_cache import InferenceCacheStore
from transcriptx.core.analysis.emotion_family.work_items import SegmentWorkItem
from transcriptx.core.analysis.hf_text_classification.runtime import LoadedClassifier
from transcriptx.core.utils.logger import log_warning

Activation = Literal["softmax", "sigmoid"]


@dataclass(frozen=True)
class ClassifierInferenceSuccess:
    kind: Literal["success"]
    scored_by_sid: Mapping[str, dict[str, Any]]
    inference_cache_hit: bool
    inference_generation_id: str


@dataclass(frozen=True)
class ClassifierInferenceFailure:
    kind: Literal["failure"]
    reason: str
    details: dict[str, Any]


ClassifierInferenceResult = ClassifierInferenceSuccess | ClassifierInferenceFailure


def resolve_classifier_scores(
    *,
    loaded: LoadedClassifier,
    expected_labels: Iterable[str],
    activation: Activation,
    batch_size: Any,
    effective_max_length: int,
    inference_key: str,
    artifact_generation_id: str,
    cache_store: InferenceCacheStore | None,
    log_prefix: str,
    work_items: Sequence[SegmentWorkItem],
    score_texts_fn: Callable[..., Sequence[Any]],
) -> ClassifierInferenceResult:
    """
    Resolve classifier scores via cache hit or batched ``score_texts_fn``.

    Cache-hit predicate (all required)::

        bool(needed_sids)
        and all(requested rows present and valid)
        and isinstance(cached_id, str) and bool(cached_id.strip())
    """
    if activation != loaded.profile.activation:
        raise ValueError(
            f"activation mismatch: helper={activation!r} "
            f"profile={loaded.profile.activation!r}"
        )

    labels = list(expected_labels)
    to_score = [item for item in work_items if is_english(item.lang) and item.text]
    needed_sids = [item.sid for item in to_score]

    scored_by_sid: dict[str, dict[str, Any]] | None = None
    inference_cache_hit = False
    inference_generation_id = artifact_generation_id

    if cache_store is not None:
        # load exceptions propagate (do not turn into misses)
        cached = cache_store.load(inference_key)
        if cached:
            rows = cached.get("rows_by_segment") or {}
            cached_id = cached.get("inference_generation_id")
            rows_ok = bool(needed_sids) and all(
                sid in rows
                and validate_classifier_cache_row(
                    rows[sid],
                    expected_labels=labels,
                    activation=activation,
                )
                for sid in needed_sids
            )
            id_ok = isinstance(cached_id, str) and bool(cached_id.strip())
            if rows_ok and id_ok:
                scored_by_sid = {sid: dict(rows[sid]) for sid in needed_sids}
                inference_cache_hit = True
                inference_generation_id = cached_id

    if scored_by_sid is not None:
        return ClassifierInferenceSuccess(
            kind="success",
            scored_by_sid=scored_by_sid,
            inference_cache_hit=inference_cache_hit,
            inference_generation_id=inference_generation_id,
        )

    # Miss path (including empty to_score)
    texts_to_score = [item.text for item in to_score]
    try:
        scored: list[Any] = []
        bs = max(1, batch_size)
        for start in range(0, len(texts_to_score), bs):
            scored.extend(
                score_texts_fn(
                    loaded,
                    texts_to_score[start : start + bs],
                    max_length=effective_max_length,
                )
            )
    except Exception as exc:
        # No helper logging — producers own inference_failed warnings.
        return ClassifierInferenceFailure(
            kind="failure",
            reason="inference_failed",
            details={"message": str(exc)},
        )

    if len(scored) != len(to_score):
        return ClassifierInferenceFailure(
            kind="failure",
            reason="scorer_cardinality_mismatch",
            details={"expected": len(to_score), "got": len(scored)},
        )

    # Conversion errors propagate (not mapped to inference_failed).
    scored_by_sid = {}
    for item, sr in zip(to_score, scored, strict=True):
        scored_by_sid[item.sid] = {
            "scores": {k: float(v) for k, v in sr.scores.items()},
            "truncated": bool(sr.truncated),
            "omitted_token_count_lower_bound": int(
                sr.omitted_token_count_lower_bound
            ),
            "scored_text_hash": item.text_hash,
        }

    if cache_store is not None:
        try:
            cache_store.store(
                inference_key,
                inference_generation_id=inference_generation_id,
                rows_by_segment=scored_by_sid,
            )
        except Exception as exc:
            log_warning(log_prefix, f"inference cache write failed: {exc}")

    return ClassifierInferenceSuccess(
        kind="success",
        scored_by_sid=scored_by_sid,
        inference_cache_hit=False,
        inference_generation_id=inference_generation_id,
    )
