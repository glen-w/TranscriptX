"""Hardening tests for emotion-family remediation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.emotion_family.cache_validation import (
    validate_classifier_cache_row,
    validate_lexical_cache_row,
)
from transcriptx.core.analysis.emotion_family.fingerprints import (
    build_compatibility_payload,
    build_display_fingerprint,
    compatibility_fingerprint,
)
from transcriptx.core.analysis.emotion_family.run_status import (
    RunStatus,
    derive_run_status_from_rows,
)
from transcriptx.core.analysis.emotion_family.source_identity import (
    SOURCE_IDENTITY_POLICY_V1,
    ensure_segment_ids,
)
from transcriptx.core.analysis.emotion_family.split_cache import AggregationCacheStore


@pytest.mark.unit
def test_ensure_segment_ids_mints_and_rejects_duplicates():
    segs = [{"text": "a"}, {"text": "b"}]
    ids = ensure_segment_ids(segs)
    assert ids == ["seg-0", "seg-1"]
    assert SOURCE_IDENTITY_POLICY_V1
    with pytest.raises(ValueError, match="duplicate"):
        ensure_segment_ids([{"id": "x"}, {"id": "x"}])


@pytest.mark.unit
def test_compatibility_separates_threshold_from_inference_identity():
    from transcriptx.core.analysis.emotion_family.fingerprints import (
        build_aggregation_settings,
    )
    from transcriptx.core.analysis.emotion_family.split_cache import (
        aggregation_settings_digest,
    )

    a = build_compatibility_payload(
        schema_version="s",
        semantics_version="v",
        effective_max_length=256,
    )
    b = build_compatibility_payload(
        schema_version="s",
        semantics_version="v",
        effective_max_length=256,
    )
    c = build_compatibility_payload(
        schema_version="s",
        semantics_version="v",
        effective_max_length=128,
    )
    # Threshold-only changes must not bust inference compatibility.
    assert compatibility_fingerprint(a) == compatibility_fingerprint(b)
    assert compatibility_fingerprint(a) != compatibility_fingerprint(c)
    s1 = build_aggregation_settings(effective_threshold=0.45)
    s2 = build_aggregation_settings(effective_threshold=0.5)
    assert aggregation_settings_digest(s1) != aggregation_settings_digest(s2)


@pytest.mark.unit
def test_display_fingerprint_independent_of_analytical():
    analytical = compatibility_fingerprint(
        build_compatibility_payload(schema_version="s", semantics_version="v")
    )
    d1 = build_display_fingerprint(family_ontology_version="ont_a", display_cap=3)
    d2 = build_display_fingerprint(family_ontology_version="ont_b", display_cap=3)
    assert d1 != d2
    assert analytical == compatibility_fingerprint(
        build_compatibility_payload(schema_version="s", semantics_version="v")
    )


@pytest.mark.unit
def test_derive_run_status_partial_on_failed_rows():
    rows = [
        {"evaluation_state": "scored"},
        {"evaluation_state": "failed"},
    ]
    status, scored, failed = derive_run_status_from_rows(rows)
    assert status == RunStatus.PARTIAL
    assert scored == 1
    assert failed == 1


@pytest.mark.unit
def test_validate_classifier_cache_row_rejects_bad_shape():
    labels = ("anger", "joy", "neutral")
    good = {
        "scores": {"anger": 0.2, "joy": 0.3, "neutral": 0.5},
        "truncated": False,
        "omitted_token_count_lower_bound": 0,
        "scored_text_hash": "abc",
    }
    assert validate_classifier_cache_row(
        good, expected_labels=labels, activation="softmax"
    )
    # Legacy omitted_token_count alias is also accepted when hash present.
    good_alias = {
        "scores": {"anger": 0.2, "joy": 0.3, "neutral": 0.5},
        "truncated": False,
        "omitted_token_count": 0,
        "scored_text_hash": "abc",
    }
    assert validate_classifier_cache_row(
        good_alias, expected_labels=labels, activation="softmax"
    )
    bad = {"scores": {"anger": 0.9}, "truncated": False, "scored_text_hash": "abc"}
    assert not validate_classifier_cache_row(
        bad, expected_labels=labels, activation="softmax"
    )
    assert not validate_classifier_cache_row(None)
    missing_hash = {
        "scores": {"anger": 0.2, "joy": 0.3, "neutral": 0.5},
        "truncated": False,
        "omitted_token_count_lower_bound": 0,
    }
    assert not validate_classifier_cache_row(
        missing_hash, expected_labels=labels, activation="softmax"
    )


@pytest.mark.unit
def test_validate_lexical_cache_row():
    assert validate_lexical_cache_row(
        {
            "evaluation_state": "scored",
            "scored_text_hash": "abc",
            "coverage": 0.5,
            "tokens_considered": 10,
            "matched_occurrences": 2,
            "assignment_counts": {"joy": 1},
            "emotion_scores": {"joy": 1.0},
        }
    )
    assert not validate_lexical_cache_row({"evaluation_state": "scored"})
    assert not validate_lexical_cache_row(
        {
            "evaluation_state": "scored",
            "coverage": 0.5,
            "tokens_considered": 10,
            "matched_occurrences": 2,
            "assignment_counts": {"joy": 1},
            "emotion_scores": {"joy": 1.0},
        }
    )


@pytest.mark.unit
def test_stable_profile_rejects_floating_revision():
    from transcriptx.core.analysis.hf_text_classification.runtime import (
        ModelProfile,
        assert_stable_revision_pinned,
    )

    profile = ModelProfile(
        profile_id="stable_test",
        model_id="org/model",
        model_revision="main",
        tokenizer_id="org/model",
        tokenizer_revision="main",
        activation="softmax",
        labels=("a", "b"),
        threshold_profile_version="t1",
        release_channel="stable",
    )
    with pytest.raises(RuntimeError, match="floating revision"):
        assert_stable_revision_pinned(profile)


@pytest.mark.unit
def test_aggregation_cache_store_roundtrip(tmp_path):
    store = AggregationCacheStore(tmp_path)
    store.store(
        "a" * 32,
        inference_generation_id="0120a4f9196a5f9eb9f523f31f914da7",
        aggregates={"speaker_stats": {"A": {"joy": 1}}},
    )
    loaded = store.load("a" * 32)
    assert loaded["inference_generation_id"] == "0120a4f9196a5f9eb9f523f31f914da7"
    assert loaded["aggregates"]["speaker_stats"]["A"]["joy"] == 1


@pytest.mark.unit
def test_persist_fails_without_generation_id():
    from transcriptx.core.analysis.emotion_family.errors import (
        EmotionFamilyPersistError,
    )
    from transcriptx.core.analysis.emotion_family.generational_store import (
        persist_generation_from_results,
    )

    with pytest.raises(EmotionFamilyPersistError, match="artifact_generation_id"):
        persist_generation_from_results(
            {"run_status": "complete"},
            SimpleNamespace(
                get_output_structure=lambda: SimpleNamespace(module_dir="/tmp")
            ),
            "emotion",
        )


@pytest.mark.unit
def test_contagion_emits_both_named_branches():
    from transcriptx.core.analysis.contagion.analysis import ContagionAnalysis
    from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash

    segments = [
        {
            "id": "s1",
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "happy",
            "start": 0.0,
            "end": 1.0,
            "nrc_emotion": {"joy": 0.9, "anger": 0.1},
            "context_emotion": "joy",
            "context_emotion_primary": "joy",
            "context_emotion_source": "contextual_emotion",
            "contextual_emotion_analytical_outcome": "labeled",
            "contextual_emotion_label": "joy",
            "contextual_emotion_confidence": 0.9,
            "contextual_emotion_scored_text_hash": segment_text_hash("happy"),
        },
        {
            "id": "s2",
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "also happy",
            "start": 1.0,
            "end": 2.0,
            "nrc_emotion": {"joy": 0.8, "anger": 0.2},
            "context_emotion": "joy",
            "context_emotion_primary": "joy",
            "context_emotion_source": "contextual_emotion",
            "contextual_emotion_analytical_outcome": "labeled",
            "contextual_emotion_label": "joy",
            "contextual_emotion_confidence": 0.8,
            "contextual_emotion_scored_text_hash": segment_text_hash("also happy"),
        },
    ]
    contextual = {
        "schema_version": "transcriptx.contextual_emotion_result.v1",
        "semantics_version": "contextual_emotion_v1",
        "module_id": "contextual_emotion",
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": 2,
        "projection_fields": [
            "segment_id",
            "evaluation_state",
            "analytical_outcome",
            "contextual_emotion_label",
            "contextual_emotion_confidence",
            "truncated",
            "canonical_ref",
        ],
        "segments_with_contextual_emotion": segments,
    }
    emotion = {
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": 2,
        "segments_with_emotion": segments,
    }
    result = ContagionAnalysis().analyze(
        [dict(s) for s in segments],
        emotion_data=emotion,
        contextual_emotion_data=contextual,
    )
    assert "lexical_emotion" in result["branches"]
    assert "contextual_emotion" in result["branches"]
    assert result["primary_branch"] == "lexical_emotion"


@pytest.mark.unit
def test_oom_does_not_mutate_cached_device():
    torch = pytest.importorskip("torch")
    from transcriptx.core.analysis.hf_text_classification.runtime import (
        ModelProfile,
        score_texts,
    )

    profile = ModelProfile(
        profile_id="oom_test",
        model_id="local",
        model_revision="0",
        tokenizer_id="local",
        tokenizer_revision="0",
        activation="softmax",
        labels=("a", "b"),
        threshold_profile_version="t0",
        max_length=8,
    )

    class FakeTok:
        def __call__(self, text, **kwargs):
            if isinstance(text, list):
                n = len(text)
                return {
                    "input_ids": torch.ones(n, 4, dtype=torch.long),
                    "attention_mask": torch.ones(n, 4, dtype=torch.long),
                }
            return {"input_ids": [1, 2, 3, 4]}

    class FakeModel:
        def __init__(self):
            self.config = MagicMock()
            self.config.id2label = {0: "a", 1: "b"}

        def __call__(self, **kwargs):
            raise RuntimeError("CUDA out of memory")

        def to(self, *args, **kwargs):
            return self

        def eval(self):
            return self

    loaded = MagicMock()
    loaded.profile = profile
    loaded.tokenizer = FakeTok()
    loaded.model = FakeModel()
    loaded.device = torch.device("cpu")
    loaded.device_class = "cuda"
    loaded.effective_max_length = 8
    loaded.resolved_id2label = {0: "a", 1: "b"}

    with pytest.raises(RuntimeError, match="refusing CPU fallback"):
        score_texts(loaded, ["hello"])
    assert loaded.device_class == "cuda"


@pytest.mark.unit
def test_label_index_order_mismatch_rejected():
    from transcriptx.core.analysis.hf_text_classification.runtime import (
        ModelProfile,
        _validate_indexed_label_map,
    )

    profile = ModelProfile(
        profile_id="order_test",
        model_id="local",
        model_revision="0",
        tokenizer_id="local",
        tokenizer_revision="0",
        activation="softmax",
        labels=("anger", "joy", "neutral"),
        threshold_profile_version="t0",
    )
    permuted = {0: "joy", 1: "anger", 2: "neutral"}
    with pytest.raises(RuntimeError, match="label index mismatch"):
        _validate_indexed_label_map(profile, permuted)
    ok = {0: "anger", 1: "joy", 2: "neutral"}
    assert _validate_indexed_label_map(profile, ok) == _validate_indexed_label_map(
        profile, dict(ok)
    )


@pytest.mark.unit
def test_language_metadata_from_transcript_level():
    from transcriptx.core.analysis.emotion_family.language import (
        extract_transcript_metadata,
        is_english,
        resolve_segment_language,
    )

    segments = [
        {
            "id": "s1",
            "text": "bonjour",
            "_transcript_metadata": {"language": "fr"},
        }
    ]
    meta = extract_transcript_metadata(segments)
    assert meta.get("language") == "fr"
    lang, tag = resolve_segment_language(segments[0], meta)
    assert lang == "fr"
    assert tag == "transcript_metadata"
    assert not is_english(lang)


@pytest.mark.unit
def test_persist_first_skips_enriched_on_failure(tmp_path):
    from transcriptx.core.analysis.contextual_emotion import ContextualEmotionAnalysis
    from transcriptx.core.analysis.emotion_family.errors import (
        EmotionFamilyPersistError,
    )

    module = ContextualEmotionAnalysis.__new__(ContextualEmotionAnalysis)
    module.module_name = "contextual_emotion"
    results = {
        "run_status": "complete",
        "usable_output": True,
        "artifact_generation_id": "0120a4f9196a5f9eb9f523f31f914da7",
        "_canonical_rows": [{"segment_id": "s1", "scores": {"joy": 1.0}}],
        "segments_with_contextual_emotion": [{"id": "s1"}],
        "global_stats": {},
        "speaker_stats": {},
        "warnings": [],
    }
    output_service = MagicMock()
    output_service.get_output_structure.return_value = MagicMock(module_dir=tmp_path)

    with (
        patch(
            "transcriptx.core.analysis.emotion_family.persist.persist_generation_from_results",
            side_effect=RuntimeError("disk full"),
        ),
        patch(
            "transcriptx.core.analysis.contextual_emotion.write_enriched_transcript"
        ) as write_enriched,
    ):
        with pytest.raises(EmotionFamilyPersistError):
            module._save_results(results, output_service)

    assert results["run_status"] == "failed"
    assert results["usable_output"] is False
    write_enriched.assert_not_called()


@pytest.mark.unit
def test_persist_success_writes_enriched_after_generation(tmp_path):
    from transcriptx.core.analysis.contextual_emotion import ContextualEmotionAnalysis
    from transcriptx.core.analysis.emotion_family.generational_store import (
        load_current_complete_rows,
    )

    module = ContextualEmotionAnalysis.__new__(ContextualEmotionAnalysis)
    module.module_name = "contextual_emotion"
    rows = [
        {
            "segment_id": "s1",
            "evaluation_state": "scored",
            "scores": {"joy": 0.9, "anger": 0.05, "neutral": 0.05},
            "scored_text_hash": "abc123",
            "truncated": False,
            "omitted_token_count_lower_bound": 0,
        }
    ]
    results = {
        "run_status": "complete",
        "usable_output": True,
        "artifact_generation_id": "02de7bdf5a35c3b1c5b3dc1809e796e1",
        "_canonical_rows": rows,
        "segments_with_contextual_emotion": [{"id": "s1", "text": "hi"}],
        "global_stats": {},
        "speaker_stats": {},
        "label_counts": {"joy": 1},
        "warnings": [],
        "release_channel": "experimental",
    }
    output_service = MagicMock()
    output_service.get_output_structure.return_value = MagicMock(module_dir=tmp_path)

    with patch(
        "transcriptx.core.analysis.contextual_emotion.write_enriched_transcript"
    ) as write_enriched:
        module._save_results(results, output_service)

    write_enriched.assert_called_once()
    loaded = load_current_complete_rows(tmp_path)
    assert loaded is not None
    assert loaded[0]["segment_id"] == "s1"
    for call in output_service.save_data.call_args_list:
        payload = call.args[0] if call.args else None
        if isinstance(payload, dict):
            assert "canonical_rows" not in payload
            assert "_canonical_rows" not in payload


@pytest.mark.unit
def test_aggregation_key_reuses_cached_inference_generation():
    from transcriptx.core.analysis.emotion_family.split_cache import (
        aggregation_cache_key,
    )

    key_a = aggregation_cache_key(
        inference_generation_id="fc621070767aa3aeb2458df762386927",
        speaker_identity_digest="spk",
        timeline_identity_digest="tl",
        aggregation_semantics_version="v1",
    )
    key_b = aggregation_cache_key(
        inference_generation_id="fc621070767aa3aeb2458df762386927",
        speaker_identity_digest="spk",
        timeline_identity_digest="tl",
        aggregation_semantics_version="v1",
    )
    key_fresh = aggregation_cache_key(
        inference_generation_id="5aecc40f292f3dc3bac459b6af81fd0e",
        speaker_identity_digest="spk",
        timeline_identity_digest="tl",
        aggregation_semantics_version="v1",
    )
    assert key_a == key_b
    assert key_a != key_fresh


@pytest.mark.unit
def test_malformed_cache_row_fails_validation():
    labels = ("anger", "joy", "neutral", "fear", "sadness", "surprise", "disgust")
    malformed = {
        "scores": {"anger": float("nan"), "joy": 0.2},
        "truncated": False,
    }
    assert not validate_classifier_cache_row(
        malformed, expected_labels=labels, activation="softmax"
    )
    incomplete = {"scores": {lab: 1.0 / 7 for lab in labels}}
    assert not validate_classifier_cache_row(
        incomplete, expected_labels=labels, activation="softmax"
    )


@pytest.mark.unit
def test_affect_tension_loads_scores_from_disk_generation(tmp_path):
    from types import SimpleNamespace

    from transcriptx.core.analysis.affect_tension import AffectTensionAnalysis
    from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash
    from transcriptx.core.analysis.emotion_family.generational_store import (
        persist_generation,
    )

    text_hash = segment_text_hash("thanks")
    persist_generation(
        tmp_path,
        module_id="contextual_emotion",
        generation_id="3b3f7911169881ccb19cd238717e9ae9",
        run_status="complete",
        usable_output=True,
        schema_version="transcriptx.contextual_emotion_result.v1",
        semantics_version="contextual_emotion_v1",
        segments_scored=1,
        canonical_rows=[
            {
                "segment_id": "s1",
                "evaluation_state": "scored",
                "analytical_outcome": "labeled",
                "scored_text_hash": text_hash,
                "scores": {"joy": 0.8, "anger": 0.1, "neutral": 0.1},
            }
        ],
    )
    enriched = [
        {
            "id": "s1",
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "thanks",
            "start": 0.0,
            "sentiment_compound_norm": -0.4,
            "context_emotion_source": "contextual_emotion",
            "contextual_emotion_analytical_outcome": "labeled",
            "context_emotion_primary": "joy",
            "contextual_emotion_label": "joy",
            "contextual_emotion_confidence": 0.8,
            "contextual_emotion_scored_text_hash": text_hash,
        }
    ]
    artifact = {
        "schema_version": "transcriptx.contextual_emotion_result.v1",
        "semantics_version": "contextual_emotion_v1",
        "module_id": "contextual_emotion",
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": 1,
        "artifact_generation_id": "3b3f7911169881ccb19cd238717e9ae9",
        "projection_fields": [
            "segment_id",
            "evaluation_state",
            "analytical_outcome",
            "contextual_emotion_label",
            "contextual_emotion_confidence",
            "truncated",
            "canonical_ref",
        ],
        "segments_with_contextual_emotion": enriched,
    }
    cfg = SimpleNamespace(analysis=SimpleNamespace(affect_tension=None))
    with patch("transcriptx.core.analysis.affect_tension.get_config", return_value=cfg):
        out = AffectTensionAnalysis().analyze(
            [dict(s) for s in enriched],
            contextual_emotion_data=artifact,
            contextual_module_dir=tmp_path,
        )
    assert out["segments"][0]["affect_contextual_metrics_status"] == "computed"
    assert out["segments"][0]["emotion_entropy"] is not None


@pytest.mark.unit
def test_affect_tension_neutral_eligible_abstained_not(tmp_path):
    from types import SimpleNamespace

    from transcriptx.core.analysis.affect_tension import AffectTensionAnalysis
    from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash

    def _run(outcome, scores, primary=""):
        from transcriptx.core.analysis.emotion_family.generational_store import (
            persist_generation,
        )

        text = "ok"
        text_hash = segment_text_hash(text)
        gid = "a" * 32 if outcome == "neutral" else "b" * 32
        row = {
            "segment_id": "s1",
            "evaluation_state": "scored",
            "analytical_outcome": outcome,
            "scored_text_hash": text_hash,
            "scores": scores,
        }
        persist_generation(
            tmp_path,
            module_id="contextual_emotion",
            generation_id=gid,
            run_status="complete",
            usable_output=True,
            canonical_rows=[row],
            schema_version="transcriptx.contextual_emotion_result.v1",
            semantics_version="contextual_emotion_v1",
            segments_scored=1,
        )
        enriched = [
            {
                "id": "s1",
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": text,
                "start": 0.0,
                "sentiment_compound_norm": 0.0,
                "context_emotion_source": "contextual_emotion",
                "contextual_emotion_analytical_outcome": outcome,
                "context_emotion_primary": primary,
                "contextual_emotion_label": primary or None,
                "contextual_emotion_scored_text_hash": text_hash,
            }
        ]
        artifact = {
            "schema_version": "transcriptx.contextual_emotion_result.v1",
            "semantics_version": "contextual_emotion_v1",
            "module_id": "contextual_emotion",
            "run_status": "complete",
            "usable_output": True,
            "segments_scored": 1,
            "artifact_generation_id": gid,
            "projection_fields": [
                "segment_id",
                "evaluation_state",
                "analytical_outcome",
                "contextual_emotion_label",
                "contextual_emotion_confidence",
                "truncated",
                "canonical_ref",
            ],
            "segments_with_contextual_emotion": enriched,
        }
        cfg = SimpleNamespace(analysis=SimpleNamespace(affect_tension=None))
        with patch(
            "transcriptx.core.analysis.affect_tension.get_config", return_value=cfg
        ):
            return AffectTensionAnalysis().analyze(
                [dict(s) for s in enriched],
                contextual_emotion_data=artifact,
                contextual_module_dir=tmp_path,
            )

    neutral = _run(
        "neutral",
        {"neutral": 0.7, "joy": 0.2, "anger": 0.1},
        primary="neutral",
    )
    assert neutral["segments"][0]["affect_contextual_metrics_status"] == "computed"

    abstained = _run(
        "abstained",
        {"neutral": 0.4, "joy": 0.3, "anger": 0.3},
        primary="",
    )
    assert abstained["segments"][0]["affect_contextual_metrics_status"] == "skipped"
    assert (
        abstained["segments"][0]["affect_contextual_metrics_reason"]
        == "abstained_ineligible"
    )


@pytest.mark.unit
def test_fine_grained_ontology_not_in_analytical_fingerprint():
    base = build_compatibility_payload(
        schema_version="fine_grained_emotion_result_schema_v1",
        semantics_version="fine_grained_emotion_v1",
        activation="sigmoid",
        effective_max_length=256,
    )
    fp1 = compatibility_fingerprint(base)
    d1 = build_display_fingerprint(family_ontology_version="ont_v1", display_cap=3)
    d2 = build_display_fingerprint(family_ontology_version="ont_v2", display_cap=3)
    assert d1 != d2
    assert fp1 == compatibility_fingerprint(base)


@pytest.mark.unit
def test_projection_fields_exclude_full_score_vectors():
    from transcriptx.core.analysis.emotion_family.consumer_contracts import (
        CONTEXTUAL_PROJECTION_SEGMENT_FIELDS,
    )

    assert "context_emotion_scores" not in CONTEXTUAL_PROJECTION_SEGMENT_FIELDS
    assert "contextual_emotion_canonical_ref" in CONTEXTUAL_PROJECTION_SEGMENT_FIELDS
    assert "context_emotion_source" in CONTEXTUAL_PROJECTION_SEGMENT_FIELDS


@pytest.mark.unit
def test_resolve_usable_max_length_caps_to_tokenizer():
    from transcriptx.core.analysis.hf_text_classification.runtime import (
        resolve_usable_max_length,
    )

    tok = MagicMock()
    tok.model_max_length = 128
    assert resolve_usable_max_length(tok, 256) == 128
    tok.model_max_length = 10_000_000
    assert resolve_usable_max_length(tok, 256) == 256


@pytest.mark.unit
def test_exclusive_mkdir_rejects_duplicate_generation_id(tmp_path):
    from transcriptx.core.analysis.emotion_family.errors import (
        EmotionFamilyGenerationExistsError,
    )
    from transcriptx.core.analysis.emotion_family.generational_store import (
        persist_generation,
    )

    kwargs = dict(
        module_id="emotion",
        generation_id="c1c8e8118e80e88beb0a7c50487145b1",
        run_status="complete",
        usable_output=True,
        canonical_rows=[
            {
                "segment_id": "s1",
                "evaluation_state": "scored",
                "scored_text_hash": "hash1",
            }
        ],
    )
    persist_generation(tmp_path, **kwargs)
    # Identical content is idempotent success.
    persist_generation(tmp_path, **kwargs)
    # Conflicting content must hard-fail.
    conflict = dict(kwargs)
    conflict["canonical_rows"] = [
        {
            "segment_id": "s1",
            "evaluation_state": "scored",
            "scored_text_hash": "different-hash",
        }
    ]
    with pytest.raises(EmotionFamilyGenerationExistsError, match="conflicting"):
        persist_generation(tmp_path, **conflict)


@pytest.mark.unit
def test_persist_helper_raises_emotion_family_persist_error(tmp_path):
    from transcriptx.core.analysis.emotion_family.errors import (
        EmotionFamilyPersistError,
    )
    from transcriptx.core.analysis.emotion_family.persist import (
        persist_canonical_then_enrich,
    )

    results = {
        "run_status": "complete",
        "usable_output": True,
        "artifact_generation_id": "643f189b612483f9d886bc2bd3fd501b",
        "_canonical_rows": [
            {
                "segment_id": "s1",
                "evaluation_state": "scored",
                "scored_text_hash": "abc",
            }
        ],
    }
    output_service = MagicMock()
    output_service.get_output_structure.return_value = MagicMock(module_dir=tmp_path)

    with patch(
        "transcriptx.core.analysis.emotion_family.persist.persist_generation_from_results",
        side_effect=RuntimeError("disk full"),
    ):
        with pytest.raises(EmotionFamilyPersistError, match="canonical persist failed"):
            persist_canonical_then_enrich(
                results=results,
                output_service=output_service,
                module_id="emotion",
                log_prefix="test",
                write_enriched=lambda: None,
            )
    assert results["run_status"] == "failed"
    assert results["usable_output"] is False


@pytest.mark.unit
def test_enriched_projection_failure_keeps_generation_complete(tmp_path):
    from transcriptx.core.analysis.emotion_family.generational_store import (
        INDEX_FILENAME,
        load_index,
    )
    from transcriptx.core.analysis.emotion_family.persist import (
        persist_canonical_then_enrich,
    )

    results = {
        "run_status": "complete",
        "usable_output": True,
        "artifact_generation_id": "3bea7d6b104f900981c4bf2a9660ac5a",
        "inference_generation_id": "9daed04d4ac0f1cd520a92f0d8f99d44",
        "schema_version": "transcriptx.emotion_result.v1",
        "semantics_version": "emotion_lexical_v2",
        "compatibility_fingerprint": "fp",
        "segments_scored": 1,
        "_canonical_rows": [
            {
                "segment_id": "s1",
                "evaluation_state": "scored",
                "scored_text_hash": "abc123",
            }
        ],
    }
    output_service = MagicMock()
    output_service.get_output_structure.return_value = MagicMock(module_dir=tmp_path)

    def boom():
        raise OSError("enriched write failed")

    persist_canonical_then_enrich(
        results=results,
        output_service=output_service,
        module_id="emotion",
        log_prefix="TEST",
        write_enriched=boom,
    )
    assert results["run_status"] == "complete"
    assert results["usable_output"] is True
    assert results["enriched_projection_status"] == "failed"
    assert "_canonical_rows" not in results
    index = load_index(tmp_path / INDEX_FILENAME)
    assert index.current_complete_generation == "3bea7d6b104f900981c4bf2a9660ac5a"


@pytest.mark.unit
def test_crash_before_index_activation_preserves_prior_complete(tmp_path, monkeypatch):
    from transcriptx.core.analysis.emotion_family.generational_store import (
        INDEX_FILENAME,
        load_index,
        persist_generation,
    )

    persist_generation(
        tmp_path,
        module_id="emotion",
        generation_id="7bab6c748870cfb2519a2bcd4e75a6f3",
        run_status="complete",
        usable_output=True,
        canonical_rows=[
            {
                "segment_id": "s1",
                "evaluation_state": "scored",
                "scored_text_hash": "h1",
            }
        ],
    )

    def boom(*args, **kwargs):
        raise RuntimeError("crash before index save")

    monkeypatch.setattr(
        "transcriptx.core.analysis.emotion_family.generational_store.save_index_atomic",
        boom,
    )
    with pytest.raises(RuntimeError, match="crash before index save"):
        persist_generation(
            tmp_path,
            module_id="emotion",
            generation_id="98a8e151ad465222d2f3af7df1f6d937",
            run_status="complete",
            usable_output=True,
            canonical_rows=[
                {
                    "segment_id": "s1",
                    "evaluation_state": "scored",
                    "scored_text_hash": "h1",
                }
            ],
        )
    index = load_index(tmp_path / INDEX_FILENAME)
    assert index.current_complete_generation == "7bab6c748870cfb2519a2bcd4e75a6f3"
    assert (tmp_path / "generations" / "98a8e151ad465222d2f3af7df1f6d937").is_dir()


@pytest.mark.unit
def test_concurrent_same_generation_id_one_wins(tmp_path):
    import threading

    from transcriptx.core.analysis.emotion_family.errors import (
        EmotionFamilyGenerationExistsError,
    )
    from transcriptx.core.analysis.emotion_family.generational_store import (
        persist_generation,
    )

    results: list[str] = []
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        try:
            persist_generation(
                tmp_path,
                module_id="emotion",
                generation_id="d0b7b6dc606d1e464522390c68db7488",
                run_status="complete",
                usable_output=True,
                canonical_rows=[
                    {
                        "segment_id": "s1",
                        "evaluation_state": "scored",
                        "scored_text_hash": "h",
                    }
                ],
            )
            results.append("ok")
        except EmotionFamilyGenerationExistsError:
            results.append("exists")
        except Exception as exc:
            # In-progress loser may see Incomplete; retry once for idempotent success.
            from transcriptx.core.analysis.emotion_family.errors import (
                EmotionFamilyGenerationIncompleteError,
            )

            if isinstance(exc, EmotionFamilyGenerationIncompleteError):
                import time

                time.sleep(0.05)
                try:
                    persist_generation(
                        tmp_path,
                        module_id="emotion",
                        generation_id="d0b7b6dc606d1e464522390c68db7488",
                        run_status="complete",
                        usable_output=True,
                        canonical_rows=[
                            {
                                "segment_id": "s1",
                                "evaluation_state": "scored",
                                "scored_text_hash": "h",
                            }
                        ],
                    )
                    results.append("ok")
                except Exception as exc2:
                    results.append(type(exc2).__name__)
            else:
                results.append(type(exc).__name__)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 2, results  # identical payload is idempotent


@pytest.mark.unit
def test_positional_max_length_cap():
    from transcriptx.core.analysis.hf_text_classification.runtime import (
        resolve_usable_max_length,
    )

    tok = MagicMock()
    tok.model_max_length = 512
    model = MagicMock()
    model.config.max_position_embeddings = 128
    assert resolve_usable_max_length(tok, 256, model=model) == 128


@pytest.mark.unit
def test_config_zero_threshold_survives_none_check():
    from pydantic import ValidationError

    from transcriptx.core.config.models.analysis_emotion_family import (
        ContextualEmotionSettingsModel,
        FineGrainedEmotionSettingsModel,
    )

    ctx = ContextualEmotionSettingsModel(confidence_threshold=0.0, batch_size=1)
    assert ctx.confidence_threshold == 0.0
    fg = FineGrainedEmotionSettingsModel(label_threshold=0.0, max_labels_per_segment=0)
    assert fg.label_threshold == 0.0
    with pytest.raises(ValidationError):
        ContextualEmotionSettingsModel(batch_size=0)


@pytest.mark.unit
def test_strict_json_rejects_nan_and_tuple_keys(tmp_path):
    from transcriptx.core.analysis.emotion_family.generational_store import (
        write_json_atomic,
    )
    from transcriptx.io.atomic_json import strict_json_dumps

    with pytest.raises(ValueError, match="non-finite"):
        strict_json_dumps({"x": float("nan")})
    with pytest.raises(TypeError, match="keys must be strings"):
        write_json_atomic(tmp_path / "bad.json", {("a", "b"): 1})


@pytest.mark.unit
def test_unsafe_generation_id_rejected(tmp_path):
    from transcriptx.core.analysis.emotion_family.errors import (
        EmotionFamilyUnsafeIdentifierError,
    )
    from transcriptx.core.analysis.emotion_family.generational_store import (
        persist_generation,
    )

    with pytest.raises(EmotionFamilyUnsafeIdentifierError):
        persist_generation(
            tmp_path,
            module_id="emotion",
            generation_id="../escape",
            run_status="failed",
            usable_output=False,
            canonical_rows=[],
        )


@pytest.mark.unit
def test_zero_hit_lexical_excluded_from_contagion_timeline():
    from transcriptx.core.analysis.contagion.detection import build_emotion_timeline

    segments = [
        {
            "id": "s1",
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "x",
            "nrc_emotion": {"anger": 0.0, "joy": 0.0},
            "emotion_evaluation_state": "scored",
        },
        {
            "id": "s2",
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "y",
            "nrc_emotion": {"joy": 0.8, "anger": 0.0},
            "emotion_evaluation_state": "scored",
        },
    ]
    _emotions, timeline = build_emotion_timeline(segments, "nrc_emotion")
    assert timeline == [("Bob", "joy")]


@pytest.mark.unit
def test_abstained_contextual_excluded_from_contagion_timeline():
    from transcriptx.core.analysis.contagion.detection import build_emotion_timeline

    segments = [
        {
            "id": "s1",
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "x",
            "context_emotion_source": "contextual_emotion",
            "contextual_emotion_analytical_outcome": "abstained",
            "contextual_emotion_label": "",
        },
        {
            "id": "s2",
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "y",
            "context_emotion_source": "contextual_emotion",
            "contextual_emotion_analytical_outcome": "neutral",
            "contextual_emotion_label": "neutral",
            "context_emotion_primary": "neutral",
        },
    ]
    _emotions, timeline = build_emotion_timeline(segments, "context_emotion")
    assert timeline == [("Bob", "neutral")]


@pytest.mark.unit
def test_detect_contagion_counts_are_json_safe():
    import json

    from transcriptx.core.analysis.contagion.detection import detect_contagion

    _events, counts, summary = detect_contagion(
        [("Alice", "joy"), ("Bob", "joy"), ("Alice", "joy"), ("Bob", "joy")]
    )
    assert isinstance(counts, list)
    assert all(isinstance(item, dict) for item in counts)
    json.dumps({"counts": counts, "summary": summary})


@pytest.mark.unit
def test_idempotent_persist_accepts_byte_equivalent(tmp_path):
    from transcriptx.core.analysis.emotion_family.generational_store import (
        persist_generation,
    )

    kwargs = dict(
        module_id="emotion",
        generation_id="d" * 32,
        run_status="complete",
        usable_output=True,
        canonical_rows=[
            {
                "segment_id": "s1",
                "evaluation_state": "scored",
                "scored_text_hash": "same",
            }
        ],
    )
    persist_generation(tmp_path, **kwargs)
    persist_generation(tmp_path, **kwargs)  # must not raise


@pytest.mark.unit
def test_builtin_profiles_pin_commit_shas():
    from transcriptx.core.analysis.hf_text_classification.profiles import (
        CONTEXTUAL_HARTMANN_V1,
        FINE_GRAINED_GOEMOTIONS_V1,
    )
    from transcriptx.core.analysis.hf_text_classification.runtime import (
        assert_revision_pinned,
    )

    assert_revision_pinned(CONTEXTUAL_HARTMANN_V1)
    assert_revision_pinned(FINE_GRAINED_GOEMOTIONS_V1)
    assert CONTEXTUAL_HARTMANN_V1.model_revision == (
        CONTEXTUAL_HARTMANN_V1.tokenizer_revision
    )
    assert len(CONTEXTUAL_HARTMANN_V1.model_revision) == 40


@pytest.mark.unit
def test_lexical_does_not_clear_contextual_fields():
    from transcriptx.core.analysis.emotion.projections import apply_lexical_projection

    seg = {
        "context_emotion": "joy",
        "context_emotion_primary": "joy",
        "context_emotion_source": "contextual_emotion",
        "contextual_emotion_label": "joy",
    }
    apply_lexical_projection(
        seg,
        {
            "nrc_emotion": {"joy": 1.0},
            "nrc_valence_scores": {},
            "nrc_emotion_coverage": 0.5,
            "evaluation_state": "scored",
            "emotion_scored_text_hash": "h",
            "canonical_ref": {"module_id": "emotion"},
        },
    )
    assert seg["context_emotion_source"] == "contextual_emotion"
    assert seg["contextual_emotion_label"] == "joy"


@pytest.mark.unit
def test_failed_contextual_envelope_has_empty_ordered_ids():
    from transcriptx.core.analysis.contextual_emotion import ContextualEmotionAnalysis
    from transcriptx.core.analysis.emotion_family.run_status import RunStatus

    module = ContextualEmotionAnalysis.__new__(ContextualEmotionAnalysis)
    module.module_name = "contextual_emotion"
    module.profile = type("P", (), {"release_channel": "experimental"})()
    result = module._failed(
        [{"id": "s1"}, {"id": "s2"}],
        "e" * 32,
        RunStatus.FAILED,
        reason="inference_failed",
        details={},
    )
    assert result["ordered_segment_ids"] == []
    assert result["_canonical_rows"] == []
    assert result["segments_scored"] == 0


@pytest.mark.unit
def test_stale_projection_cleared_when_generation_mismatches():
    from transcriptx.core.analysis.emotion_family.consumer_contracts import (
        merge_contextual_projection,
    )
    from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash

    text = "hello"
    text_hash = segment_text_hash(text)
    segments = [
        {
            "id": "s1",
            "text": text,
            "context_emotion_source": "contextual_emotion",
            "contextual_emotion_scored_text_hash": text_hash,
            "contextual_emotion_canonical_ref": {
                "artifact_generation_id": "a" * 32,
            },
            "contextual_emotion_label": "joy",
        }
    ]
    artifact = {
        "artifact_generation_id": "b" * 32,
        "segments_with_contextual_emotion": [],
    }
    merged = merge_contextual_projection(segments, artifact)
    assert merged == 0
    assert "context_emotion_source" not in segments[0]


@pytest.mark.unit
def test_after_enrich_failure_keeps_canonical_complete(tmp_path):
    from transcriptx.core.analysis.emotion_family.generational_store import (
        INDEX_FILENAME,
        load_index,
    )
    from transcriptx.core.analysis.emotion_family.persist import (
        persist_canonical_then_enrich,
    )

    results = {
        "run_status": "complete",
        "usable_output": True,
        "artifact_generation_id": "f" * 32,
        "schema_version": "transcriptx.emotion_result.v1",
        "semantics_version": "emotion_lexical_v2",
        "segments_scored": 1,
        "_canonical_rows": [
            {
                "segment_id": "s1",
                "evaluation_state": "scored",
                "scored_text_hash": "abc",
            }
        ],
    }
    output_service = MagicMock()
    output_service.get_output_structure.return_value = MagicMock(module_dir=tmp_path)

    persist_canonical_then_enrich(
        results=results,
        output_service=output_service,
        module_id="emotion",
        log_prefix="TEST",
        write_enriched=lambda: None,
        after_enrich=lambda: (_ for _ in ()).throw(RuntimeError("chart boom")),
    )
    assert results["run_status"] == "complete"
    assert results["usable_output"] is True
    assert results["secondary_output_status"] == "failed"
    index = load_index(tmp_path / INDEX_FILENAME)
    assert index.current_complete_generation == "f" * 32
