"""Unit tests for emotion-family canonical hashing and run status."""

from __future__ import annotations

import unicodedata

import pytest

from transcriptx.core.analysis.emotion_family.canonical_hash import (
    canonical_json_dumps,
    canonical_json_hash,
)
from transcriptx.core.analysis.emotion_family.consumer_contracts import (
    CONTEXTUAL_EMOTION_FOR_CONTAGION,
    evaluate_optional_producer,
)
from transcriptx.core.analysis.emotion_family.fingerprints import (
    segment_text_hash,
    text_source_digest,
)
from transcriptx.core.analysis.emotion_family.run_status import (
    RunStatus,
    derive_usable_output,
)


@pytest.mark.unit
def test_canonical_json_hash_stable_across_key_order():
    a = canonical_json_hash({"b": 1, "a": 2})
    b = canonical_json_hash({"a": 2, "b": 1})
    assert a == b


@pytest.mark.unit
def test_canonical_dumps_no_spaces():
    s = canonical_json_dumps({"z": True, "a": None})
    assert " " not in s
    assert s.startswith("{")


@pytest.mark.unit
def test_usable_output_requires_scored_segments():
    assert (
        derive_usable_output(run_status=RunStatus.COMPLETE, segments_scored=0) is False
    )
    assert (
        derive_usable_output(run_status=RunStatus.COMPLETE, segments_scored=1) is True
    )
    assert (
        derive_usable_output(run_status=RunStatus.PARTIAL, segments_scored=5) is False
    )


@pytest.mark.unit
def test_text_source_digest_preserves_order_not_lexical_sort():
    segs_a = [
        {"id": "b", "text": "one"},
        {"id": "a", "text": "two"},
    ]
    segs_b = [
        {"id": "a", "text": "two"},
        {"id": "b", "text": "one"},
    ]
    assert text_source_digest(segs_a) != text_source_digest(segs_b)


@pytest.mark.unit
def test_segment_text_hash_nfc():
    composed = "café"
    decomposed = unicodedata.normalize("NFD", composed)
    assert segment_text_hash(composed) == segment_text_hash(decomposed)


@pytest.mark.unit
def test_optional_producer_complete_zero_scored_not_applicable():
    artifact = {
        "schema_version": "transcriptx.contextual_emotion_result.v1",
        "semantics_version": "contextual_emotion_v1",
        "module_id": "contextual_emotion",
        "run_status": "complete",
        "usable_output": False,
        "segments_scored": 0,
    }
    ev = evaluate_optional_producer(
        CONTEXTUAL_EMOTION_FOR_CONTAGION, selected=True, artifact=artifact
    )
    assert ev.satisfied is False
    assert ev.reason == "dependency_not_applicable"


@pytest.mark.unit
def test_optional_producer_partial_skipped():
    artifact = {
        "schema_version": "transcriptx.contextual_emotion_result.v1",
        "semantics_version": "contextual_emotion_v1",
        "module_id": "contextual_emotion",
        "run_status": "partial",
        "usable_output": False,
        "segments_scored": 3,
    }
    ev = evaluate_optional_producer(
        CONTEXTUAL_EMOTION_FOR_CONTAGION, selected=True, artifact=artifact
    )
    assert ev.reason == "dependency_partial"


def _usable_contextual_artifact(segments):
    return {
        "schema_version": "transcriptx.contextual_emotion_result.v1",
        "semantics_version": "contextual_emotion_v1",
        "module_id": "contextual_emotion",
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": len(segments),
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


@pytest.mark.unit
def test_merge_contextual_projection_requires_provenance():
    from transcriptx.core.analysis.emotion_family.consumer_contracts import (
        merge_contextual_projection,
    )

    provenance_seg = {
        "id": "s1",
        "start": 0.0,
        "text": "a",
        "context_emotion": "joy",
        "context_emotion_primary": "joy",
        "context_emotion_scores": {"joy": 0.9},
        "context_emotion_source": "contextual_emotion",
        "contextual_emotion_scored_text_hash": segment_text_hash("a"),
    }
    legacy_seg = {
        "id": "s2",
        "start": 1.0,
        "text": "b",
        "context_emotion": "anger",
        "context_emotion_scores": {"anger": 0.8},
        # no context_emotion_source — legacy NRC-filled, UI-only
    }
    artifact = _usable_contextual_artifact([provenance_seg, legacy_seg])
    consumer_segments = [
        {"id": "s1", "start": 0.0, "text": "a"},
        {"id": "s2", "start": 1.0, "text": "b"},
    ]
    merged = merge_contextual_projection(consumer_segments, artifact)
    assert merged == 1
    assert consumer_segments[0]["context_emotion_source"] == "contextual_emotion"
    assert consumer_segments[0]["context_emotion"] == "joy"
    assert "context_emotion" not in consumer_segments[1]


@pytest.mark.unit
def test_affect_tension_contextual_gated_by_contract(monkeypatch):
    """Unsatisfied producer contract → contextual scores never read."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from transcriptx.core.analysis.affect_tension import AffectTensionAnalysis

    segments = [
        {
            "id": "s1",
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "thanks",
            "start": 0.0,
            "sentiment_compound_norm": -0.4,
            "context_emotion_primary": "joy",
            "context_emotion_source": "contextual_emotion",
            "contextual_emotion_analytical_outcome": "labeled",
        }
    ]
    cfg = SimpleNamespace(analysis=SimpleNamespace(affect_tension=None))
    module = AffectTensionAnalysis()
    with patch("transcriptx.core.analysis.affect_tension.get_config", return_value=cfg):
        # No producer artifact → not_selected → contextual branch off.
        out = module.analyze(segments)
    branches = out["metadata"]["emotion_branches"]
    assert branches["contextual_emotion_segments"] == 0
    assert branches["contextual_contract"]["satisfied"] is False
    assert branches["contextual_contract"]["reason"] == "not_selected"
    assert out["segments"][0]["affect_mismatch_posneg"] is None
    assert out["segments"][0]["affect_contextual_metrics_status"] == "skipped"


@pytest.mark.unit
def test_affect_tension_contextual_active_when_contract_satisfied(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import patch

    from transcriptx.core.analysis.affect_tension import AffectTensionAnalysis
    from transcriptx.core.analysis.emotion_family.generational_store import (
        persist_generation,
    )

    text_hash = segment_text_hash("thanks")
    gid = "c" * 32
    row = {
        "segment_id": "s1",
        "evaluation_state": "scored",
        "analytical_outcome": "labeled",
        "scored_text_hash": text_hash,
        "scores": {"joy": 0.8, "anger": 0.1, "neutral": 0.1},
    }
    persist_generation(
        tmp_path,
        module_id="contextual_emotion",
        generation_id=gid,
        run_status="complete",
        usable_output=True,
        schema_version="transcriptx.contextual_emotion_result.v1",
        semantics_version="contextual_emotion_v1",
        segments_scored=1,
        canonical_rows=[row],
    )
    enriched = [
        {
            "id": "s1",
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "thanks",
            "start": 0.0,
            "sentiment_compound_norm": -0.4,
            "context_emotion": "joy",
            "context_emotion_primary": "joy",
            "context_emotion_source": "contextual_emotion",
            "contextual_emotion_analytical_outcome": "labeled",
            "contextual_emotion_label": "joy",
            "contextual_emotion_confidence": 0.8,
            "contextual_emotion_scored_text_hash": text_hash,
        }
    ]
    artifact = _usable_contextual_artifact(enriched)
    artifact["artifact_generation_id"] = gid
    cfg = SimpleNamespace(analysis=SimpleNamespace(affect_tension=None))
    module = AffectTensionAnalysis()
    with patch("transcriptx.core.analysis.affect_tension.get_config", return_value=cfg):
        out = module.analyze(
            [dict(s) for s in enriched],
            contextual_emotion_data=artifact,
            contextual_module_dir=tmp_path,
        )
    branches = out["metadata"]["emotion_branches"]
    assert branches["contextual_contract"]["satisfied"] is True
    assert branches["contextual_emotion_segments"] == 1
    assert out["segments"][0]["affect_contextual_metrics_status"] == "computed"
    assert out["segments"][0]["emotion_entropy"] is not None


@pytest.mark.unit
def test_affect_tension_abstained_ineligible():
    from types import SimpleNamespace
    from unittest.mock import patch

    from transcriptx.core.analysis.affect_tension import AffectTensionAnalysis

    text_hash = segment_text_hash("meh")
    enriched = [
        {
            "id": "s1",
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "meh",
            "start": 0.0,
            "sentiment_compound_norm": 0.0,
            "context_emotion_source": "contextual_emotion",
            "contextual_emotion_analytical_outcome": "abstained",
            "context_emotion_primary": "",
            "contextual_emotion_scored_text_hash": text_hash,
        }
    ]
    artifact = _usable_contextual_artifact(enriched)
    artifact["_canonical_rows"] = [
        {
            "segment_id": "s1",
            "evaluation_state": "scored",
            "analytical_outcome": "abstained",
            "scored_text_hash": text_hash,
            "scores": {"joy": 0.3, "neutral": 0.4, "anger": 0.3},
        }
    ]
    cfg = SimpleNamespace(analysis=SimpleNamespace(affect_tension=None))
    module = AffectTensionAnalysis()
    with patch("transcriptx.core.analysis.affect_tension.get_config", return_value=cfg):
        out = module.analyze(
            [dict(s) for s in enriched], contextual_emotion_data=artifact
        )
    assert out["segments"][0]["affect_contextual_metrics_status"] == "skipped"
    assert (
        out["segments"][0]["affect_contextual_metrics_reason"] == "abstained_ineligible"
    )
    assert out["metadata"]["emotion_branches"]["contextual_emotion_segments"] == 0


@pytest.mark.unit
def test_optional_producer_missing_projection_evidence_fails_closed():
    artifact = {
        "schema_version": "transcriptx.contextual_emotion_result.v1",
        "semantics_version": "contextual_emotion_v1",
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": 2,
        "module_id": "contextual_emotion",
        # neither sample_projection nor projection_fields
    }
    ev = evaluate_optional_producer(
        CONTEXTUAL_EMOTION_FOR_CONTAGION, selected=True, artifact=artifact
    )
    assert ev.satisfied is False
    assert ev.reason == "dependency_incompatible"
    assert ev.details.get("missing_projection_evidence") is True


@pytest.mark.unit
def test_optional_producer_wrong_module_id_incompatible():
    artifact = {
        "schema_version": "transcriptx.contextual_emotion_result.v1",
        "semantics_version": "contextual_emotion_v1",
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": 2,
        "module_id": "emotion",
        "projection_fields": list(
            CONTEXTUAL_EMOTION_FOR_CONTAGION.required_projection_fields
        ),
    }
    ev = evaluate_optional_producer(
        CONTEXTUAL_EMOTION_FOR_CONTAGION, selected=True, artifact=artifact
    )
    assert ev.reason == "dependency_incompatible"
    assert ev.details.get("field") == "producer_module_id"


@pytest.mark.unit
def test_optional_producer_missing_module_id_fails_closed():
    artifact = {
        "schema_version": "transcriptx.contextual_emotion_result.v1",
        "semantics_version": "contextual_emotion_v1",
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": 2,
        "projection_fields": list(
            CONTEXTUAL_EMOTION_FOR_CONTAGION.required_projection_fields
        ),
    }
    ev = evaluate_optional_producer(
        CONTEXTUAL_EMOTION_FOR_CONTAGION, selected=True, artifact=artifact
    )
    assert ev.satisfied is False
    assert ev.reason == "dependency_incompatible"
    assert ev.details.get("missing_module_id") is True


@pytest.mark.unit
def test_merge_rejects_missing_scored_text_hash():
    from transcriptx.core.analysis.emotion_family.consumer_contracts import (
        merge_contextual_projection,
    )

    src = {
        "id": "s1",
        "start": 0.0,
        "text": "hello",
        "context_emotion": "joy",
        "context_emotion_primary": "joy",
        "context_emotion_source": "contextual_emotion",
        # missing contextual_emotion_scored_text_hash
    }
    artifact = _usable_contextual_artifact([src])
    consumer = [{"id": "s1", "start": 0.0, "text": "hello"}]
    assert merge_contextual_projection(consumer, artifact) == 0


@pytest.mark.unit
def test_merge_rejects_timestamp_fallback_and_hash_mismatch():
    from transcriptx.core.analysis.emotion_family.consumer_contracts import (
        merge_contextual_projection,
    )
    from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash

    src = {
        "id": "s1",
        "start": 0.0,
        "text": "hello world",
        "context_emotion": "joy",
        "context_emotion_primary": "joy",
        "context_emotion_source": "contextual_emotion",
        "contextual_emotion_scored_text_hash": segment_text_hash("hello world"),
    }
    artifact = _usable_contextual_artifact([src])
    # Different id, same start — must NOT merge via timestamp
    consumer = [{"id": "other", "start": 0.0, "text": "hello world"}]
    assert merge_contextual_projection(consumer, artifact) == 0
    # Matching id but different text hash — reject
    consumer2 = [{"id": "s1", "start": 0.0, "text": "different text"}]
    assert merge_contextual_projection(consumer2, artifact) == 0
    # Matching id + hash — accept
    consumer3 = [{"id": "s1", "start": 0.0, "text": "hello world"}]
    assert merge_contextual_projection(consumer3, artifact) == 1
    assert consumer3[0]["context_emotion_source"] == "contextual_emotion"
