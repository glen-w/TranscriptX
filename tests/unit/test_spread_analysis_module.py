"""Offline unit tests for contagion analysis (filename avoids auto-marker)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.contagion.analysis import ContagionAnalysis
from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash


def _seg(speaker: str, text: str, start: float, **extra):
    sid = extra.pop("id", None) or f"{speaker}-{start}"
    return {
        "id": sid,
        "segment_id": sid,
        "speaker": speaker,
        "speaker_db_id": hash(speaker) % 1000 + 1,
        "text": text,
        "start": start,
        "end": start + 1.0,
        **extra,
    }


def _contextual_artifact(segments, **overrides):
    artifact = {
        "module_id": "contextual_emotion",
        "schema_version": "contextual_emotion_result_schema_v2",
        "semantics_version": "contextual_emotion_v1",
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": max(len(segments), 1),
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
    artifact.update(overrides)
    return artifact


def _lexical_artifact(segments, **overrides):
    artifact = {
        "module_id": "emotion",
        "schema_version": "emotion_result_schema_v2",
        "semantics_version": "emotion_lexical_v2",
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": len(segments),
        "segments_with_emotion": segments,
        "projection_fields": [
            "segment_id",
            "evaluation_state",
            "nrc_emotion",
            "nrc_emotion_coverage",
            "emotion_scored_text_hash",
            "canonical_ref",
        ],
    }
    artifact.update(overrides)
    return artifact


def _with_contextual_projection(seg: dict) -> dict:
    text = seg.get("text") or ""
    out = dict(seg)
    out.setdefault("context_emotion_source", "contextual_emotion")
    out.setdefault("contextual_emotion_analytical_outcome", "labeled")
    out.setdefault(
        "contextual_emotion_label",
        out.get("context_emotion_primary") or out.get("context_emotion") or "joy",
    )
    out.setdefault("context_emotion_primary", out["contextual_emotion_label"])
    out.setdefault("context_emotion", out["contextual_emotion_label"])
    out.setdefault("contextual_emotion_confidence", 0.9)
    out["contextual_emotion_scored_text_hash"] = segment_text_hash(text)
    return out


def _with_lexical_projection(seg: dict) -> dict:
    text = seg.get("text") or ""
    out = dict(seg)
    out.setdefault("nrc_emotion", {"joy": 0.9})
    out.setdefault("nrc_emotion_coverage", 1.0)
    out.setdefault("emotion_evaluation_state", "scored")
    out["emotion_scored_text_hash"] = segment_text_hash(text)
    out.setdefault(
        "emotion_canonical_ref",
        {
            "module_id": "emotion",
            "artifact_generation_id": "a" * 32,
            "schema_version": "emotion_result_schema_v2",
            "semantics_version": "emotion_lexical_v2",
            "row_key": str(out.get("id") or ""),
            "scored_text_hash": out["emotion_scored_text_hash"],
            "integrity_checksum": "b" * 64,
        },
    )
    return out


@pytest.mark.unit
def test_analyze_contextual_branch_requires_contract() -> None:
    module = ContagionAnalysis()
    enriched = [
        _with_contextual_projection(_seg("Alice", "happy", 0.0, context_emotion="joy")),
        _with_contextual_projection(_seg("Bob", "also", 1.0, context_emotion="joy")),
    ]
    plain = [_seg("Alice", "happy", 0.0), _seg("Bob", "also", 1.0)]
    result = module.analyze(
        plain, contextual_emotion_data=_contextual_artifact(enriched)
    )
    assert result["emotion_type"] == "context_emotion"
    assert result["branch_decision"]["contextual"]["satisfied"] is True
    assert "contagion_events" in result
    assert "timeline" in result


@pytest.mark.unit
def test_analyze_legacy_context_fields_never_satisfy_contextual_branch() -> None:
    """Legacy NRC-filled context_emotion_* without provenance is UI-only."""
    module = ContagionAnalysis()
    segments = [
        _seg(
            "Alice",
            "happy",
            0.0,
            context_emotion_primary="joy",
            context_emotion_scores={"joy": 0.9},
        ),
        _seg("Bob", "also", 1.0, context_emotion_scores={"joy": 0.8}),
    ]
    result = module.analyze(segments)
    assert result["run_status"] == "not_applicable"
    assert result["usable_output"] is False
    assert result["emotion_type"] is None


@pytest.mark.unit
def test_analyze_with_nrc_emotion() -> None:
    module = ContagionAnalysis()
    segments = [
        _seg("Alice", "a", 0.0, nrc_emotion={"joy": 0.9, "anger": 0.0}),
        _seg("Bob", "b", 1.0, nrc_emotion={"joy": 0.7}),
    ]
    result = module.analyze(segments)
    assert result["emotion_type"] == "nrc_emotion"
    assert result["branch_decision"]["contextual"]["reason"] == "not_selected"


@pytest.mark.unit
def test_analyze_merges_lexical_from_emotion_artifact() -> None:
    module = ContagionAnalysis()
    plain = [_seg("Alice", "a", 0.0), _seg("Bob", "b", 1.0)]
    enriched = [
        _with_lexical_projection(_seg("Alice", "a", 0.0, nrc_emotion={"joy": 0.9})),
        _with_lexical_projection(_seg("Bob", "b", 1.0, nrc_emotion={"joy": 0.7})),
    ]
    result = module.analyze(plain, emotion_data=_lexical_artifact(enriched))
    assert result["emotion_type"] == "nrc_emotion"


@pytest.mark.unit
def test_analyze_skips_contextual_when_producer_partial() -> None:
    module = ContagionAnalysis()
    enriched = [
        _with_lexical_projection(
            _with_contextual_projection(
                _seg("Alice", "a", 0.0, nrc_emotion={"joy": 0.9}, context_emotion="joy")
            )
        ),
        _with_lexical_projection(
            _with_contextual_projection(
                _seg("Bob", "b", 1.0, nrc_emotion={"joy": 0.7}, context_emotion="joy")
            )
        ),
    ]
    partial = _contextual_artifact(enriched, run_status="partial", usable_output=False)
    result = module.analyze(
        [dict(s) for s in enriched],
        emotion_data=_lexical_artifact(enriched),
        contextual_emotion_data=partial,
    )
    assert result["emotion_type"] == "nrc_emotion"
    assert result["branch_decision"]["contextual"]["satisfied"] is False
    assert result["branch_decision"]["contextual"]["reason"] == "dependency_partial"


@pytest.mark.unit
def test_analyze_skips_contextual_when_zero_scored() -> None:
    module = ContagionAnalysis()
    plain = [_seg("Alice", "a", 0.0, nrc_emotion={"joy": 0.5})]
    zero = _contextual_artifact([], run_status="complete", usable_output=False)
    zero["segments_scored"] = 0
    result = module.analyze(plain, contextual_emotion_data=zero)
    assert result["emotion_type"] == "nrc_emotion"
    assert (
        result["branch_decision"]["contextual"]["reason"] == "dependency_not_applicable"
    )


@pytest.mark.unit
def test_analyze_not_applicable_when_missing_signals() -> None:
    module = ContagionAnalysis()
    result = module.analyze(
        [_seg("Alice", "x", 0.0)],
        emotion_data=_lexical_artifact([{"text": "no emotions"}]),
    )
    assert result["run_status"] == "not_applicable"
    assert result["usable_output"] is False


@pytest.mark.unit
def test_analyze_not_applicable_when_emotion_data_none() -> None:
    module = ContagionAnalysis()
    result = module.analyze([_seg("Alice", "x", 0.0)], emotion_data=None)
    assert result["run_status"] == "not_applicable"


@pytest.mark.unit
def test_analyze_lexical_not_usable_gated() -> None:
    module = ContagionAnalysis()
    enriched = [
        _with_lexical_projection(_seg("Alice", "a", 0.0, nrc_emotion={"joy": 0.9}))
    ]
    not_usable = _lexical_artifact(enriched, run_status="complete", usable_output=False)
    not_usable["segments_scored"] = 0
    result = module.analyze([_seg("Alice", "a", 0.0)], emotion_data=not_usable)
    assert result["run_status"] == "not_applicable"


@pytest.mark.unit
def test_selected_but_missing_artifact_is_dependency_failed() -> None:
    module = ContagionAnalysis()
    result = module.analyze(
        [_seg("Alice", "x", 0.0)],
        contextual_emotion_data=None,
        contextual_selected=True,
    )
    assert result["branch_decision"]["contextual"]["reason"] == "dependency_failed"
    assert result["run_status"] == "not_applicable"


@pytest.mark.unit
def test_run_from_context_success_with_contextual_producer(tmp_path) -> None:
    module = ContagionAnalysis()
    enriched = [
        _with_contextual_projection(_seg("Alice", "a", 0.0, context_emotion="joy")),
        _with_contextual_projection(_seg("Bob", "b", 1.0, context_emotion="joy")),
    ]
    contextual_result = _contextual_artifact(enriched)

    def get_result(name):
        if name == "contextual_emotion":
            return contextual_result
        return None

    context = SimpleNamespace(
        transcript_path=str(tmp_path / "t.json"),
        get_segments=lambda: [_seg("Alice", "a", 0.0), _seg("Bob", "b", 1.0)],
        get_analysis_result=get_result,
        get_computed_value=lambda key: (
            ["contextual_emotion", "contagion"] if key == "selected_modules" else None
        ),
        get_transcript_dir=lambda: str(tmp_path),
        get_run_id=lambda: "run-1",
        get_runtime_flags=lambda: {},
        store_analysis_result=MagicMock(),
    )

    fake_out = MagicMock()
    fake_out.get_output_structure.return_value = SimpleNamespace(
        module_dir=tmp_path / "c"
    )

    with (
        patch(
            "transcriptx.core.output.output_service.create_output_service",
            return_value=fake_out,
        ),
        patch.object(module, "save_results"),
    ):
        result = module.run_from_context(context)
    assert result["status"] == "success"
    assert result["results"]["emotion_type"] == "context_emotion"
    context.store_analysis_result.assert_called()


@pytest.mark.unit
def test_run_from_context_not_applicable_without_emotion() -> None:
    module = ContagionAnalysis()
    context = SimpleNamespace(
        transcript_path="/tmp/t.json",
        get_segments=lambda: [_seg("Alice", "x", 0.0)],
        get_analysis_result=lambda name: None,
        get_computed_value=lambda key: None,
        get_transcript_dir=lambda: "/tmp",
        get_run_id=lambda: "r",
        get_runtime_flags=lambda: {},
        store_analysis_result=lambda *a, **k: None,
    )
    fake_out = MagicMock()
    fake_out.get_output_structure.return_value = SimpleNamespace(module_dir="/tmp/c")
    with (
        patch(
            "transcriptx.core.output.output_service.create_output_service",
            return_value=fake_out,
        ),
        patch.object(module, "save_results"),
    ):
        result = module.run_from_context(context)
    assert result["status"] == "success"
    assert result["results"]["run_status"] == "not_applicable"


@pytest.mark.unit
def test_save_results_writes_summary_and_matrix(monkeypatch) -> None:
    module = ContagionAnalysis()
    results = {
        "contagion_events": [
            {"from": "Alice", "to": "Bob", "emotion": "joy"},
            {"from": "Alice", "to": "Bob", "emotion": "joy"},
        ],
        "contagion_summary": {"pair": 1},
        "contagion_counts": [
            {"actor": "Alice", "target": "Bob", "emotion": "joy", "count": 2}
        ],
        "emotion_type": "context_emotion",
        "branch_decision": {},
        "branches": {},
    }
    output = MagicMock()
    output.get_output_structure.return_value = SimpleNamespace()
    output.save_data = MagicMock()
    output.save_summary = MagicMock()
    create_matrix = MagicMock()
    monkeypatch.setattr(
        "transcriptx.core.analysis.contagion.analysis.create_contagion_matrix",
        create_matrix,
    )
    module._save_results(results, output)
    create_matrix.assert_called_once()
    assert output.save_summary.called
    assert any(
        c.args[1] == "contagion_summary" and isinstance(c.args[0], str)
        for c in output.save_data.call_args_list
    )


@pytest.mark.unit
def test_save_results_no_events_message(monkeypatch) -> None:
    module = ContagionAnalysis()
    results = {
        "contagion_events": [],
        "contagion_summary": {},
        "contagion_counts": {},
        "emotion_type": "nrc_emotion",
        "branch_decision": {},
        "branches": {},
    }
    output = MagicMock()
    output.get_output_structure.return_value = SimpleNamespace()
    monkeypatch.setattr(
        "transcriptx.core.analysis.contagion.analysis.create_contagion_matrix",
        MagicMock(),
    )
    module._save_results(results, output)
    txt_payload = next(
        c.args[0]
        for c in output.save_data.call_args_list
        if c.args[1] == "contagion_summary" and isinstance(c.args[0], str)
    )
    assert "No significant" in txt_payload
