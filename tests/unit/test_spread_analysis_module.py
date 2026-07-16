"""Offline unit tests for contagion analysis (filename avoids auto-marker)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.contagion.analysis import ContagionAnalysis


def _seg(speaker: str, text: str, start: float, **extra):
    return {
        "speaker": speaker,
        "speaker_db_id": hash(speaker) % 1000 + 1,
        "text": text,
        "start": start,
        "end": start + 1.0,
        **extra,
    }


@pytest.mark.unit
def test_analyze_with_context_emotion_primary_and_scores() -> None:
    module = ContagionAnalysis()
    segments = [
        _seg(
            "Alice",
            "happy",
            0.0,
            context_emotion_primary="joy",
            context_emotion_scores={"joy": 0.9},
        ),
        _seg(
            "Bob",
            "also",
            1.0,
            context_emotion_scores={"joy": 0.8, "sadness": 0.0},
        ),
    ]
    result = module.analyze(segments)
    assert result["emotion_type"] == "context_emotion"
    assert "contagion_events" in result
    assert "timeline" in result


@pytest.mark.unit
def test_analyze_with_nrc_emotion() -> None:
    module = ContagionAnalysis()
    segments = [
        _seg("Alice", "a", 0.0, nrc_emotion={"joy": 0.9, "anger": 0.0}),
        _seg("Bob", "b", 1.0, nrc_emotion={"joy": 0.7}),
    ]
    result = module.analyze(segments)
    assert result["emotion_type"] == "nrc_emotion"


@pytest.mark.unit
def test_analyze_uses_emotion_data_segments_directly() -> None:
    module = ContagionAnalysis()
    plain = [_seg("Alice", "a", 0.0), _seg("Bob", "b", 1.0)]
    enriched = [
        _seg("Alice", "a", 0.0, context_emotion="joy"),
        _seg("Bob", "b", 1.0, context_emotion="joy"),
    ]
    result = module.analyze(plain, emotion_data={"segments_with_emotion": enriched})
    assert result["emotion_type"] == "context_emotion"


@pytest.mark.unit
def test_analyze_merges_then_reconstructs(monkeypatch) -> None:
    module = ContagionAnalysis()
    plain = [_seg("Alice", "a", 0.0), _seg("Bob", "b", 1.0)]
    # segments_with_emotion present but without usable emotion fields
    weak = [{"text": "x"}, {"text": "y"}]
    emotion_data = {
        "segments_with_emotion": weak,
        "contextual_all": {"Alice": ["joy"], "Bob": ["joy"]},
    }

    monkeypatch.setattr(
        "transcriptx.core.analysis.contagion.analysis.merge_emotion_data",
        lambda segs, sw, logger: (segs, None, False),
    )

    def fake_recon(segs, edata, logger):
        out = [
            {**segs[0], "context_emotion": "joy"},
            {**segs[1], "context_emotion": "joy"},
        ]
        return out, "context_emotion", True

    monkeypatch.setattr(
        "transcriptx.core.analysis.contagion.analysis.reconstruct_emotion_data",
        fake_recon,
    )
    result = module.analyze(plain, emotion_data=emotion_data)
    assert result["emotion_type"] == "context_emotion"


@pytest.mark.unit
def test_analyze_raises_detailed_when_missing() -> None:
    module = ContagionAnalysis()
    with pytest.raises(ValueError, match="Please run emotion analysis first"):
        module.analyze(
            [_seg("Alice", "x", 0.0)],
            emotion_data={"segments_with_emotion": [{"text": "no emotions"}]},
        )


@pytest.mark.unit
def test_analyze_raises_when_emotion_data_none() -> None:
    module = ContagionAnalysis()
    with pytest.raises(ValueError, match="emotion_data is None"):
        module.analyze([_seg("Alice", "x", 0.0)], emotion_data=None)


@pytest.mark.unit
def test_run_from_context_success_loads_enriched(tmp_path, monkeypatch) -> None:
    module = ContagionAnalysis()
    enriched_path = tmp_path / "enriched.json"
    enriched_path.write_text("[]")
    segs = [
        _seg("Alice", "a", 0.0, context_emotion="joy"),
        _seg("Bob", "b", 1.0, context_emotion="joy"),
    ]
    emotion_result = {"segments_with_emotion": [{"text": "stale"}]}  # no emotion keys

    context = SimpleNamespace(
        transcript_path=str(tmp_path / "t.json"),
        get_segments=lambda: [_seg("Alice", "a", 0.0), _seg("Bob", "b", 1.0)],
        get_analysis_result=lambda name: emotion_result if name == "emotion" else None,
        get_transcript_dir=lambda: str(tmp_path),
        get_run_id=lambda: "run-1",
        get_runtime_flags=lambda: {},
        store_analysis_result=MagicMock(),
    )

    fake_out = MagicMock()
    fake_out.get_output_structure.return_value = SimpleNamespace(
        module_dir=tmp_path / "c"
    )

    monkeypatch.setattr(
        "transcriptx.core.utils._path_core.find_enriched_transcript",
        lambda path, mod: enriched_path,
    )
    monkeypatch.setattr(
        "transcriptx.io.transcript_loader.load_transcript",
        lambda path: {"segments": segs},
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
def test_run_from_context_error_envelope() -> None:
    module = ContagionAnalysis()
    context = SimpleNamespace(
        transcript_path="/tmp/t.json",
        get_segments=lambda: [_seg("Alice", "x", 0.0)],
        get_analysis_result=lambda name: None,
        get_transcript_dir=lambda: "/tmp",
        get_run_id=lambda: "r",
        get_runtime_flags=lambda: {},
        store_analysis_result=lambda *a, **k: None,
    )
    result = module.run_from_context(context)
    assert result["status"] == "error"
    assert result["results"] == {}


@pytest.mark.unit
def test_save_results_writes_summary_and_matrix(monkeypatch) -> None:
    module = ContagionAnalysis()
    results = {
        "contagion_events": [
            {"from": "Alice", "to": "Bob", "emotion": "joy"},
            {"from": "Alice", "to": "Bob", "emotion": "joy"},
        ],
        "contagion_summary": {"pair": 1},
        "contagion_counts": {("Alice", "Bob", "joy"): 2},
        "emotion_type": "context_emotion",
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
    texts = [
        c.args[0]
        for c in output.save_data.call_args_list
        if c.kwargs.get("format_type") == "txt" or (len(c.args) > 2 and False)
    ]
    # At least one txt summary call
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
