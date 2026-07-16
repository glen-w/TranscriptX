"""Offline unit helpers/branches for dynamics echoes analysis."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from transcriptx.core.analysis.dynamics.echoes import (
    EXPLICIT_QUOTE_PATTERNS,
    EchoesAnalysis,
)
from transcriptx.core.models.events import Event


def _seg(speaker: str, text: str, start: float, end: float | None = None):
    return {
        "speaker": speaker,
        "text": text,
        "start": start,
        "end": end if end is not None else start + 1.0,
    }


@pytest.fixture
def echoes(monkeypatch) -> EchoesAnalysis:
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            semantic_model_name="unused",
            echoes=SimpleNamespace(
                lookback_seconds=240.0,
                max_candidates=50,
                min_tokens=5,
                lexical_echo_threshold=0.5,
                paraphrase_threshold=0.7,
                explicit_quote_weight=1.0,
                enable_semantic_paraphrase=False,
                exclude_phrases=["ok", "yeah"],
                echo_burst_window_seconds=25.0,
                echo_burst_min_events=3,
                echo_burst_percentile_threshold=0.5,
                semantic_model_name=None,
            ),
        )
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.dynamics.echoes.get_config", lambda: cfg
    )
    return EchoesAnalysis()


@pytest.mark.unit
def test_trivial_token_and_candidates(echoes: EchoesAnalysis) -> None:
    assert echoes._is_trivial("")
    assert echoes._is_trivial("ok")
    assert not echoes._is_trivial("we should ship tomorrow please")
    assert echoes._token_count("a  b   c") == 3

    segments = [
        _seg("Alice", "one two three four five six", 0.0),
        _seg("Bob", "seven eight nine ten eleven twelve", 10.0),
        _seg("Alice", "as you said we should ship tomorrow", 20.0),
    ]
    cands = echoes._collect_candidates(
        segments, 2, lookback_seconds=15.0, max_candidates=1
    )
    assert cands == [1]


@pytest.mark.unit
def test_speaker_for_segment_fallback(echoes: EchoesAnalysis) -> None:
    assert echoes._speaker_for_segment({"speaker": "SPEAKER_00"}, []) == "SPEAKER_00"
    assert echoes._speaker_for_segment({}, []) == "UNKNOWN"


@pytest.mark.unit
def test_analyze_empty_and_explicit_quote(echoes: EchoesAnalysis) -> None:
    assert echoes.analyze([]) == {"events": [], "stats": {}, "echo_network": []}

    segments = [
        _seg("Alice", "We should ship tomorrow after the smoke tests pass.", 0.0),
        _seg(
            "Bob",
            "As you said, we should ship tomorrow after the smoke tests pass.",
            3.0,
        ),
    ]
    result = echoes.analyze(segments, transcript_hash="hash1")
    kinds = {e.kind for e in result["events"]}
    assert "explicit_quote" in kinds
    assert result["echo_network"]
    assert EXPLICIT_QUOTE_PATTERNS


@pytest.mark.unit
def test_analyze_lexical_echo_with_stubbed_similarity(
    echoes: EchoesAnalysis, monkeypatch
) -> None:
    monkeypatch.setattr(
        echoes.similarity,
        "calculate_text_similarity",
        lambda a, b, method="tfidf": 0.9,
    )
    segments = [
        _seg("Alice", "alpha beta gamma delta epsilon zeta", 0.0),
        _seg("Bob", "alpha beta gamma delta epsilon eta", 5.0),
        _seg("Carol", "alpha beta gamma delta epsilon theta", 6.0),
    ]
    result = echoes.analyze(segments, transcript_hash="h")
    assert any(e.kind == "echo" for e in result["events"])
    speakers_in_network = {
        (r["from_speaker"], r["to_speaker"]) for r in result["echo_network"]
    }
    assert speakers_in_network


@pytest.mark.unit
def test_analyze_paraphrase_path(echoes: EchoesAnalysis, monkeypatch) -> None:
    echoes.config.enable_semantic_paraphrase = True

    class FakeModel:
        def encode(self, texts, show_progress_bar=False):
            # Identical vectors → similarity 1.0
            return np.ones((len(texts), 4), dtype=float)

    monkeypatch.setattr(echoes, "_get_embedding_model", lambda: FakeModel())
    segments = [
        _seg("Alice", "alpha beta gamma delta epsilon zeta", 0.0),
        _seg("Bob", "alpha beta gamma delta epsilon eta", 5.0),
    ]
    result = echoes.analyze(segments, transcript_hash="h")
    assert any(e.kind == "paraphrase" for e in result["events"])


@pytest.mark.unit
def test_detect_echo_bursts(echoes: EchoesAnalysis) -> None:
    events = [
        Event(
            event_id=f"e{i}",
            kind="echo",
            time_start=float(i),
            time_end=float(i) + 0.5,
            speaker="Bob",
            segment_start_idx=0,
            segment_end_idx=i,
            severity=0.5,
            score=0.8,
        )
        for i in range(5)
    ]
    bursts = echoes._detect_echo_bursts(events, "hash")
    assert bursts
    assert bursts[0].kind == "echo_burst"
    assert echoes._detect_echo_bursts([], "h") == []


@pytest.mark.unit
def test_get_embedding_model_handles_import_failure(
    echoes: EchoesAnalysis, monkeypatch
):
    monkeypatch.setitem(
        __import__("sys").modules,
        "sentence_transformers",
        None,
    )
    echoes._embedding_model = None
    assert echoes._get_embedding_model() is None


@pytest.mark.unit
def test_run_from_context_success_and_error(
    tmp_path, echoes: EchoesAnalysis, monkeypatch
):
    context = SimpleNamespace(
        transcript_path=str(tmp_path / "t.json"),
        transcript_key="k",
        get_segments=lambda: [
            _seg("Alice", "We should ship tomorrow after the smoke tests pass.", 0.0),
            _seg(
                "Bob",
                "As you said, we should ship tomorrow after the smoke tests pass.",
                3.0,
            ),
        ],
        get_transcript_dir=lambda: str(tmp_path),
        get_run_id=lambda: "r1",
        get_runtime_flags=lambda: {},
        store_analysis_result=MagicMock(),
    )
    fake_out = MagicMock()
    fake_out.get_output_structure.return_value = SimpleNamespace(
        module_dir=tmp_path / "echoes"
    )
    with (
        patch(
            "transcriptx.core.output.output_service.create_output_service",
            return_value=fake_out,
        ),
        patch.object(echoes, "save_results"),
    ):
        ok = echoes.run_from_context(context)
    assert ok["status"] == "success"

    bad = SimpleNamespace(
        transcript_path=str(tmp_path / "t.json"),
        transcript_key="k",
        get_segments=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        get_transcript_dir=lambda: str(tmp_path),
        get_run_id=lambda: "r1",
        get_runtime_flags=lambda: {},
        store_analysis_result=lambda *a, **k: None,
    )
    err = echoes.run_from_context(bad)
    assert err["status"] == "error"


@pytest.mark.unit
def test_save_results_writes_heatmap_and_timeline(
    tmp_path, echoes: EchoesAnalysis, monkeypatch
) -> None:
    from transcriptx.core.output.output_service import create_output_service
    from transcriptx.core.utils import output_standards as output_standards_module
    from transcriptx.core.utils import paths as paths_module

    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir()
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))

    segments = [
        _seg("Alice", "We should ship tomorrow after the smoke tests pass.", 0.0),
        _seg(
            "Bob",
            "As you said, we should ship tomorrow after the smoke tests pass.",
            3.0,
        ),
    ]
    results = echoes.analyze(segments, transcript_hash="h")
    transcript_path = str(outputs_root / "dummy.json")
    __import__("pathlib").Path(transcript_path).write_text("{}")
    output_service = create_output_service(
        transcript_path, "echoes", output_dir=str(outputs_root)
    )
    echoes.save_results(results, output_service=output_service)
    data_dir = output_service.get_output_structure().global_data_dir
    assert (data_dir / "echoes.events.json").exists()
    assert (data_dir / "echoes.stats.json").exists()
