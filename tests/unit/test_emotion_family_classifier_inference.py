"""Unit tests for emotion_family.classifier_inference."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.emotion_family.classifier_inference import (
    ClassifierInferenceFailure,
    ClassifierInferenceSuccess,
    resolve_classifier_scores,
)
from transcriptx.core.analysis.emotion_family.work_items import SegmentWorkItem
from transcriptx.core.analysis.hf_text_classification.profiles import (
    CONTEXTUAL_HARTMANN_V1,
    FINE_GRAINED_GOEMOTIONS_V1,
)
from transcriptx.core.analysis.hf_text_classification.runtime import (
    LoadedClassifier,
    ScoreResult,
)

ARTIFACT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CACHED = "cccccccccccccccccccccccccccccccc"
LABELS_SOFT = list(CONTEXTUAL_HARTMANN_V1.labels)
LABELS_SIG = list(FINE_GRAINED_GOEMOTIONS_V1.labels)


def _loaded(profile) -> LoadedClassifier:
    return LoadedClassifier(
        profile=profile,
        model=MagicMock(),
        tokenizer=MagicMock(),
        device="cpu",
        device_class="cpu",
        dtype="float32",
        cache_key="k",
        effective_max_length=64,
        resolved_label_map_hash="h",
        resolved_id2label={i: lab for i, lab in enumerate(profile.labels)},
    )


def _work(*texts_langs) -> tuple[SegmentWorkItem, ...]:
    items = []
    for i, (text, lang) in enumerate(texts_langs):
        seg = {"id": str(i + 1), "text": text, "language": lang}
        items.append(
            SegmentWorkItem(
                seg=seg,
                sid=str(i + 1),
                speaker="A",
                lang=lang,
                lang_res="segment_override",
                text=(text or "").strip(),
                text_hash=f"hash-{i+1}",
            )
        )
    return tuple(items)


def _row(labels, top="joy"):
    scores = {lab: 0.02 for lab in labels}
    scores[top] = 1.0 - 0.02 * (len(labels) - 1)
    return {
        "scores": scores,
        "truncated": False,
        "omitted_token_count_lower_bound": 0,
        "scored_text_hash": "h",
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "profile,activation,labels",
    [
        (CONTEXTUAL_HARTMANN_V1, "softmax", LABELS_SOFT),
        (FINE_GRAINED_GOEMOTIONS_V1, "sigmoid", LABELS_SIG),
    ],
)
def test_miss_scores_and_store(profile, activation, labels):
    loaded = _loaded(profile)
    store = MagicMock()
    store.load.return_value = None
    calls = []

    def score_fn(ld, texts, max_length=None):
        calls.append((ld, list(texts), max_length))
        out = []
        for t in texts:
            scores = {lab: 0.01 for lab in labels}
            if activation == "softmax":
                scores = {lab: 0.02 for lab in labels}
                scores["joy"] = 1.0 - 0.02 * (len(labels) - 1)
            else:
                scores["joy"] = 0.8
            out.append(
                ScoreResult(
                    scores=scores,
                    truncated=False,
                    omitted_token_count_lower_bound=0,
                    device_class="cpu",
                    dtype="float32",
                )
            )
        return out

    result = resolve_classifier_scores(
        loaded=loaded,
        expected_labels=labels,
        activation=activation,
        batch_size=8,
        effective_max_length=64,
        inference_key="key1",
        artifact_generation_id=ARTIFACT,
        cache_store=store,
        log_prefix="TEST",
        work_items=_work(("hello", "en"), ("bonjour", "fr")),
        score_texts_fn=score_fn,
    )
    assert isinstance(result, ClassifierInferenceSuccess)
    assert result.inference_cache_hit is False
    assert result.inference_generation_id == ARTIFACT
    assert set(result.scored_by_sid) == {"1"}
    assert calls[0][0] is loaded
    assert calls[0][1] == ["hello"]
    assert calls[0][2] == 64
    store.store.assert_called_once()
    kwargs = store.store.call_args
    assert kwargs.args[0] == "key1"
    assert kwargs.kwargs["inference_generation_id"] == ARTIFACT
    row = kwargs.kwargs["rows_by_segment"]["1"]
    assert set(row) == {
        "scores",
        "truncated",
        "omitted_token_count_lower_bound",
        "scored_text_hash",
    }
    assert "omitted_token_count" not in row
    assert "speaker" not in row


@pytest.mark.unit
@pytest.mark.parametrize(
    "activation,profile,labels",
    [
        ("softmax", CONTEXTUAL_HARTMANN_V1, LABELS_SOFT),
        ("sigmoid", FINE_GRAINED_GOEMOTIONS_V1, LABELS_SIG),
    ],
)
def test_cache_hit_fresh_dicts_and_id(activation, profile, labels):
    loaded = _loaded(profile)
    payload_row = _row(labels)
    payload_row["scored_text_hash"] = "hash-1"
    store = MagicMock()
    store.load.return_value = {
        "inference_generation_id": CACHED,
        "rows_by_segment": {
            "1": payload_row,
            "orphan": {"scores": {}},  # unrelated malformed
        },
    }
    score_fn = MagicMock(side_effect=AssertionError("should not score"))
    result = resolve_classifier_scores(
        loaded=loaded,
        expected_labels=labels,
        activation=activation,
        batch_size=8,
        effective_max_length=64,
        inference_key="k",
        artifact_generation_id=ARTIFACT,
        cache_store=store,
        log_prefix="TEST",
        work_items=_work(("hello", "en")),
        score_texts_fn=score_fn,
    )
    assert result.inference_cache_hit is True
    assert result.inference_generation_id == CACHED
    assert set(result.scored_by_sid) == {"1"}
    assert result.scored_by_sid is not store.load.return_value["rows_by_segment"]
    assert result.scored_by_sid["1"] is not payload_row
    score_fn.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize("bad_id", [None, "", "   ", 12345])
def test_blank_or_non_string_inference_id_is_miss(bad_id):
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    row = _row(LABELS_SOFT)
    row["scored_text_hash"] = "hash-1"
    store = MagicMock()
    store.load.return_value = {
        "inference_generation_id": bad_id,
        "rows_by_segment": {"1": row},
    }
    scored = [
        ScoreResult(
            scores=_row(LABELS_SOFT)["scores"],
            truncated=False,
            omitted_token_count_lower_bound=0,
            device_class="cpu",
            dtype="float32",
        )
    ]
    result = resolve_classifier_scores(
        loaded=loaded,
        expected_labels=LABELS_SOFT,
        activation="softmax",
        batch_size=8,
        effective_max_length=64,
        inference_key="k",
        artifact_generation_id=ARTIFACT,
        cache_store=store,
        log_prefix="TEST",
        work_items=_work(("hello", "en")),
        score_texts_fn=lambda *a, **k: scored,
    )
    assert result.inference_cache_hit is False
    assert result.inference_generation_id == ARTIFACT


@pytest.mark.unit
def test_empty_needed_sids_writes_empty_cache_and_not_vacuous_hit():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    store = MagicMock()
    store.load.return_value = {
        "inference_generation_id": CACHED,
        "rows_by_segment": {"1": _row(LABELS_SOFT)},
    }
    score_fn = MagicMock()
    result = resolve_classifier_scores(
        loaded=loaded,
        expected_labels=LABELS_SOFT,
        activation="softmax",
        batch_size=8,
        effective_max_length=64,
        inference_key="k",
        artifact_generation_id=ARTIFACT,
        cache_store=store,
        log_prefix="TEST",
        work_items=_work(("", "en"), ("bonjour", "fr")),
        score_texts_fn=score_fn,
    )
    assert result.scored_by_sid == {}
    assert result.inference_cache_hit is False
    score_fn.assert_not_called()
    store.store.assert_called_once_with(
        "k",
        inference_generation_id=ARTIFACT,
        rows_by_segment={},
    )


@pytest.mark.unit
def test_score_exception_no_helper_log():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    store = MagicMock()
    store.load.return_value = None
    with patch(
        "transcriptx.core.analysis.emotion_family.classifier_inference.log_warning"
    ) as log:
        result = resolve_classifier_scores(
            loaded=loaded,
            expected_labels=LABELS_SOFT,
            activation="softmax",
            batch_size=8,
            effective_max_length=64,
            inference_key="k",
            artifact_generation_id=ARTIFACT,
            cache_store=store,
            log_prefix="TEST",
            work_items=_work(("hello", "en")),
            score_texts_fn=MagicMock(side_effect=RuntimeError("boom")),
        )
    assert isinstance(result, ClassifierInferenceFailure)
    assert result.reason == "inference_failed"
    assert result.details == {"message": "boom"}
    log.assert_not_called()
    store.store.assert_not_called()


@pytest.mark.unit
def test_multi_batch_exception_discards_partial():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    store = MagicMock()
    store.load.return_value = None
    calls = {"n": 0}

    def score_fn(ld, texts, max_length=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return [
                ScoreResult(
                    scores=_row(LABELS_SOFT)["scores"],
                    truncated=False,
                    omitted_token_count_lower_bound=0,
                    device_class="cpu",
                    dtype="float32",
                )
            ]
        raise RuntimeError("batch2")

    result = resolve_classifier_scores(
        loaded=loaded,
        expected_labels=LABELS_SOFT,
        activation="softmax",
        batch_size=1,
        effective_max_length=64,
        inference_key="k",
        artifact_generation_id=ARTIFACT,
        cache_store=store,
        log_prefix="TEST",
        work_items=_work(("a", "en"), ("b", "en")),
        score_texts_fn=score_fn,
    )
    assert result.kind == "failure"
    store.store.assert_not_called()


@pytest.mark.unit
def test_cardinality_mismatch_totals():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    store = MagicMock()
    store.load.return_value = None

    def score_fn(ld, texts, max_length=None):
        return []  # each batch empty → total 0

    result = resolve_classifier_scores(
        loaded=loaded,
        expected_labels=LABELS_SOFT,
        activation="softmax",
        batch_size=1,
        effective_max_length=64,
        inference_key="k",
        artifact_generation_id=ARTIFACT,
        cache_store=store,
        log_prefix="TEST",
        work_items=_work(("a", "en"), ("b", "en")),
        score_texts_fn=score_fn,
    )
    assert result.reason == "scorer_cardinality_mismatch"
    assert result.details == {"expected": 2, "got": 0}


@pytest.mark.unit
def test_activation_mismatch_raises():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    with pytest.raises(ValueError, match="activation mismatch"):
        resolve_classifier_scores(
            loaded=loaded,
            expected_labels=LABELS_SOFT,
            activation="sigmoid",
            batch_size=8,
            effective_max_length=64,
            inference_key="k",
            artifact_generation_id=ARTIFACT,
            cache_store=None,
            log_prefix="TEST",
            work_items=_work(("a", "en")),
            score_texts_fn=MagicMock(),
        )


@pytest.mark.unit
def test_load_exception_propagates():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    store = MagicMock()
    store.load.side_effect = ValueError("unsafe cache key")
    with pytest.raises(ValueError, match="unsafe"):
        resolve_classifier_scores(
            loaded=loaded,
            expected_labels=LABELS_SOFT,
            activation="softmax",
            batch_size=8,
            effective_max_length=64,
            inference_key="k",
            artifact_generation_id=ARTIFACT,
            cache_store=store,
            log_prefix="TEST",
            work_items=_work(("a", "en")),
            score_texts_fn=MagicMock(),
        )


@pytest.mark.unit
def test_expected_labels_generator_materialized_once():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    store = MagicMock()
    row = _row(LABELS_SOFT)
    row["scored_text_hash"] = "hash-1"
    store.load.return_value = {
        "inference_generation_id": CACHED,
        "rows_by_segment": {"1": row, "2": dict(row, scored_text_hash="hash-2")},
    }
    gen = (lab for lab in LABELS_SOFT)
    result = resolve_classifier_scores(
        loaded=loaded,
        expected_labels=gen,
        activation="softmax",
        batch_size=8,
        effective_max_length=64,
        inference_key="k",
        artifact_generation_id=ARTIFACT,
        cache_store=store,
        log_prefix="TEST",
        work_items=_work(("a", "en"), ("b", "en")),
        score_texts_fn=MagicMock(side_effect=AssertionError("no")),
    )
    assert result.inference_cache_hit is True


@pytest.mark.unit
def test_cache_write_failure_still_success():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    store = MagicMock()
    store.load.return_value = None
    store.store.side_effect = OSError("disk")
    scored = [
        ScoreResult(
            scores=_row(LABELS_SOFT)["scores"],
            truncated=False,
            omitted_token_count_lower_bound=0,
            device_class="cpu",
            dtype="float32",
        )
    ]
    with patch(
        "transcriptx.core.analysis.emotion_family.classifier_inference.log_warning"
    ) as log:
        result = resolve_classifier_scores(
            loaded=loaded,
            expected_labels=LABELS_SOFT,
            activation="softmax",
            batch_size=8,
            effective_max_length=64,
            inference_key="k",
            artifact_generation_id=ARTIFACT,
            cache_store=store,
            log_prefix="CTX",
            work_items=_work(("a", "en")),
            score_texts_fn=lambda *a, **k: scored,
        )
    assert result.kind == "success"
    log.assert_called()
    assert "CTX" in log.call_args.args[0]


@pytest.mark.unit
def test_conversion_failure_propagates_no_cache_write():
    """Malformed ScoreResult conversion must propagate (not inference_failed)."""
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    store = MagicMock()
    store.load.return_value = None

    class _Bad:
        # missing .scores → AttributeError on conversion
        truncated = False
        omitted_token_count_lower_bound = 0

    with pytest.raises(AttributeError):
        resolve_classifier_scores(
            loaded=loaded,
            expected_labels=LABELS_SOFT,
            activation="softmax",
            batch_size=8,
            effective_max_length=64,
            inference_key="k",
            artifact_generation_id=ARTIFACT,
            cache_store=store,
            log_prefix="TEST",
            work_items=_work(("hello", "en")),
            score_texts_fn=lambda *a, **k: [_Bad()],
        )
    store.store.assert_not_called()


@pytest.mark.unit
def test_invalid_requested_row_is_full_miss():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    store = MagicMock()
    store.load.return_value = {
        "inference_generation_id": CACHED,
        "rows_by_segment": {"1": {"scores": {}, "truncated": False}},  # invalid
    }
    scored = [
        ScoreResult(
            scores=_row(LABELS_SOFT)["scores"],
            truncated=False,
            omitted_token_count_lower_bound=0,
            device_class="cpu",
            dtype="float32",
        )
    ]
    result = resolve_classifier_scores(
        loaded=loaded,
        expected_labels=LABELS_SOFT,
        activation="softmax",
        batch_size=8,
        effective_max_length=64,
        inference_key="k",
        artifact_generation_id=ARTIFACT,
        cache_store=store,
        log_prefix="TEST",
        work_items=_work(("hello", "en")),
        score_texts_fn=lambda *a, **k: scored,
    )
    assert result.inference_cache_hit is False
    assert result.inference_generation_id == ARTIFACT


@pytest.mark.unit
def test_cache_unavailable_none_store_misses_without_store():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    scored = [
        ScoreResult(
            scores=_row(LABELS_SOFT)["scores"],
            truncated=False,
            omitted_token_count_lower_bound=0,
            device_class="cpu",
            dtype="float32",
        )
    ]
    result = resolve_classifier_scores(
        loaded=loaded,
        expected_labels=LABELS_SOFT,
        activation="softmax",
        batch_size=8,
        effective_max_length=64,
        inference_key="k",
        artifact_generation_id=ARTIFACT,
        cache_store=None,
        log_prefix="TEST",
        work_items=_work(("hello", "en")),
        score_texts_fn=lambda *a, **k: scored,
    )
    assert result.kind == "success"
    assert result.inference_cache_hit is False


@pytest.mark.unit
def test_call_order_activation_then_cache_then_score_on_miss():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    order: list[str] = []

    class _Store:
        def load(self, key):
            order.append("cache_load")
            return None

        def store(self, *a, **k):
            order.append("cache_store")

    def score_fn(*a, **k):
        order.append("score")
        return [
            ScoreResult(
                scores=_row(LABELS_SOFT)["scores"],
                truncated=False,
                omitted_token_count_lower_bound=0,
                device_class="cpu",
                dtype="float32",
            )
        ]

    # Activation mismatch before any cache touch
    with pytest.raises(ValueError, match="activation mismatch"):
        resolve_classifier_scores(
            loaded=loaded,
            expected_labels=LABELS_SOFT,
            activation="sigmoid",
            batch_size=8,
            effective_max_length=64,
            inference_key="k",
            artifact_generation_id=ARTIFACT,
            cache_store=_Store(),
            log_prefix="TEST",
            work_items=_work(("hello", "en")),
            score_texts_fn=score_fn,
        )
    assert order == []

    resolve_classifier_scores(
        loaded=loaded,
        expected_labels=LABELS_SOFT,
        activation="softmax",
        batch_size=8,
        effective_max_length=64,
        inference_key="k",
        artifact_generation_id=ARTIFACT,
        cache_store=_Store(),
        log_prefix="TEST",
        work_items=_work(("hello", "en")),
        score_texts_fn=score_fn,
    )
    assert order == ["cache_load", "score", "cache_store"]


@pytest.mark.unit
def test_empty_cache_write_later_read_still_miss(tmp_path):
    from transcriptx.core.analysis.emotion_family.split_cache import InferenceCacheStore

    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    store = InferenceCacheStore(tmp_path / "inf")
    result = resolve_classifier_scores(
        loaded=loaded,
        expected_labels=LABELS_SOFT,
        activation="softmax",
        batch_size=8,
        effective_max_length=64,
        inference_key="emptykey0123456789abcdef0123456789abcdef0123456789ab",
        artifact_generation_id=ARTIFACT,
        cache_store=store,
        log_prefix="TEST",
        work_items=_work(("", "en")),
        score_texts_fn=MagicMock(side_effect=AssertionError("no score")),
    )
    assert result.scored_by_sid == {}
    assert result.inference_cache_hit is False
    # Later resolve with still-empty eligibility remains a miss (not vacuous hit).
    again = resolve_classifier_scores(
        loaded=loaded,
        expected_labels=LABELS_SOFT,
        activation="softmax",
        batch_size=8,
        effective_max_length=64,
        inference_key="emptykey0123456789abcdef0123456789abcdef0123456789ab",
        artifact_generation_id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        cache_store=store,
        log_prefix="TEST",
        work_items=_work(("", "en")),
        score_texts_fn=MagicMock(side_effect=AssertionError("no score")),
    )
    assert again.inference_cache_hit is False
    assert again.inference_generation_id == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


@pytest.mark.unit
def test_batch_size_preserves_max_one_without_int_coercion():
    loaded = _loaded(CONTEXTUAL_HARTMANN_V1)
    store = MagicMock()
    store.load.return_value = None
    batches: list[int] = []

    def score_fn(ld, texts, max_length=None):
        batches.append(len(texts))
        return [
            ScoreResult(
                scores=_row(LABELS_SOFT)["scores"],
                truncated=False,
                omitted_token_count_lower_bound=0,
                device_class="cpu",
                dtype="float32",
            )
            for _ in texts
        ]

    resolve_classifier_scores(
        loaded=loaded,
        expected_labels=LABELS_SOFT,
        activation="softmax",
        batch_size=0,  # max(1, 0) == 1
        effective_max_length=64,
        inference_key="k",
        artifact_generation_id=ARTIFACT,
        cache_store=store,
        log_prefix="TEST",
        work_items=_work(("a", "en"), ("b", "en"), ("c", "en")),
        score_texts_fn=score_fn,
    )
    assert batches == [1, 1, 1]
