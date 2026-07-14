"""Tests for echoes."""

from __future__ import annotations

import csv
import types
from pathlib import Path

from transcriptx.core.analysis.dynamics.echoes import EchoesAnalysis


def test_echoes_detect_explicit_quote_and_echo() -> None:
    segments = [
        {
            "speaker": "Alice",
            "text": "We should ship tomorrow, after the smoke tests pass.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "Bob",
            "text": "As you said, we should ship tomorrow after the smoke tests pass.",
            "start": 3.0,
            "end": 5.0,
        },
    ]
    results = EchoesAnalysis().analyze(segments)
    kinds = {event.kind for event in results["events"]}
    assert "explicit_quote" in kinds
    # Lexical echo threshold/config may change; explicit_quote is the stable contract here.


def test_echoes_detects_cross_speaker_quote_with_diarized_labels() -> None:
    """Regression: diarization-only labels must still yield cross-speaker echoes."""
    segments = [
        {
            "speaker": "SPEAKER_00",
            "text": "We should ship tomorrow, after the smoke tests pass.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "SPEAKER_01",
            "text": "As you said, we should ship tomorrow after the smoke tests pass.",
            "start": 3.0,
            "end": 5.0,
        },
    ]
    results = EchoesAnalysis().analyze(segments)
    assert results["events"], "expected at least one echo event for diarized speakers"
    kinds = {event.kind for event in results["events"]}
    assert "explicit_quote" in kinds
    # The explicit-quote event must attribute distinct (non-UNKNOWN) speakers.
    speakers = {e.speaker for e in results["events"] if e.kind == "explicit_quote"}
    assert speakers and "UNKNOWN" not in speakers


def test_echoes_single_diarized_speaker_has_no_cross_speaker_events() -> None:
    """A single speaker (even diarized) must not echo themselves cross-speaker."""
    segments = [
        {
            "speaker": "SPEAKER_00",
            "text": "We should ship tomorrow, after the smoke tests pass.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "SPEAKER_00",
            "text": "As you said, we should ship tomorrow after the smoke tests pass.",
            "start": 3.0,
            "end": 5.0,
        },
    ]
    results = EchoesAnalysis().analyze(segments)
    cross_kinds = {"explicit_quote", "echo", "paraphrase"}
    assert not [e for e in results["events"] if e.kind in cross_kinds]


def test_echoes_save_results_writes_diarized_artifacts(tmp_path, monkeypatch) -> None:
    """End-to-end: analyze + save_results emit artifacts for diarized speakers."""
    from transcriptx.core.output.output_service import create_output_service
    from transcriptx.core.utils import output_standards as output_standards_module
    from transcriptx.core.utils import paths as paths_module

    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir()
    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))

    segments = [
        {
            "speaker": "SPEAKER_00",
            "text": "We should ship tomorrow, after the smoke tests pass.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "SPEAKER_01",
            "text": "As you said, we should ship tomorrow after the smoke tests pass.",
            "start": 3.0,
            "end": 5.0,
        },
    ]
    analysis = EchoesAnalysis()
    results = analysis.analyze(segments)
    assert results["echo_network"], "expected a cross-speaker echo edge"

    transcript_path = str(outputs_root / "dummy_transcript.json")
    Path(transcript_path).write_text("{}")
    output_service = create_output_service(
        transcript_path, "echoes", output_dir=str(outputs_root)
    )
    analysis.save_results(results, output_service=output_service)

    data_dir = Path(output_service.get_output_structure().global_data_dir)
    events_path = data_dir / "echoes.events.json"
    network_path = data_dir / "echo_network.csv"
    assert events_path.exists(), "echoes.events.json was not written"
    assert network_path.exists(), "echo_network.csv was not written"

    rows = list(csv.reader(network_path.open()))
    flat = {cell for row in rows for cell in row}
    assert "SPEAKER_00" in flat and "SPEAKER_01" in flat


def test_echoes_uses_configured_semantic_model(monkeypatch) -> None:
    selected_model_name = {}

    class _FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            selected_model_name["value"] = model_name

    fake_module = types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer)
    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", fake_module)

    fake_cfg = types.SimpleNamespace(
        analysis=types.SimpleNamespace(
            semantic_model_name="sentence-transformers/custom-semantic-model",
            echoes=types.SimpleNamespace(semantic_model_name=None),
        )
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.dynamics.echoes.get_config", lambda: fake_cfg
    )

    analysis = EchoesAnalysis()
    analysis._get_embedding_model()

    assert selected_model_name["value"] == "sentence-transformers/custom-semantic-model"
