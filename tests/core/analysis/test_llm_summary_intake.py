"""Intake-focused unit tests for llm_summary / llm_speaker_summary response shapes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.llm_speaker_summary import LLMSpeakerSummaryAnalysis
from transcriptx.core.analysis.llm_summary import LLMSummaryAnalysis
from transcriptx.core.llm.errors import LLM_INVALID_RESPONSE, LLMResponseError
from transcriptx.core.utils.config.main import TranscriptXConfig
from tests.fixtures.llm_responses import TEXT_SUMMARY_FIXTURES, TextSummaryFixture


def _mini_segments() -> list[dict]:
    return [
        {"speaker": "Alice", "text": "Hello there.", "start": 0.0, "end": 1.0},
        {"speaker": "Bob", "text": "Hi Alice.", "start": 1.0, "end": 2.0},
    ]


def _cfg() -> TranscriptXConfig:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    return cfg


@pytest.mark.unit
@pytest.mark.parametrize(
    "fixture",
    [f for f in TEXT_SUMMARY_FIXTURES if f.expect == "non_empty"],
    ids=[f.id for f in TEXT_SUMMARY_FIXTURES if f.expect == "non_empty"],
)
def test_llm_summary_accepts_model_family_prose(
    tmp_path, fixture: TextSummaryFixture
) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_segments.return_value = _mini_segments()
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}

    mock_client = MagicMock()
    mock_client.model = fixture.model_id
    mock_client.generate.return_value = fixture.body

    with (
        patch(
            "transcriptx.core.analysis.llm_summary.get_config",
            return_value=_cfg(),
        ),
        patch(
            "transcriptx.core.analysis.llm_summary.build_ollama_analysis_client",
            return_value=mock_client,
        ),
        patch(
            "transcriptx.core.analysis.llm_summary.write_llm_artifacts",
            return_value=("a.json", "a.md"),
        ),
        patch("transcriptx.core.analysis.llm_summary.create_output_service") as mock_os,
    ):
        mock_os.return_value.get_output_structure.return_value = SimpleNamespace(
            module_dir=str(tmp_path / "out" / "llm_summary")
        )
        mock_os.return_value.get_artifacts.return_value = []
        result = LLMSummaryAnalysis().run_from_context(context)

    assert result["status"] == "success"
    assert result["payload"]["summary"] == fixture.body.strip()


@pytest.mark.unit
def test_llm_summary_thinking_empty_client_error_surfaces(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_segments.return_value = _mini_segments()
    context.get_runtime_flags.return_value = {}

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.side_effect = LLMResponseError(
        "Ollama response missing non-empty 'response' field"
    )

    with (
        patch(
            "transcriptx.core.analysis.llm_summary.get_config",
            return_value=_cfg(),
        ),
        patch(
            "transcriptx.core.analysis.llm_summary.build_ollama_analysis_client",
            return_value=mock_client,
        ),
    ):
        with pytest.raises(LLMResponseError) as exc:
            LLMSummaryAnalysis().run_from_context(context)
    assert exc.value.error_code == LLM_INVALID_RESPONSE


@pytest.mark.unit
def test_llm_speaker_summary_thinking_empty_marks_speaker_failed(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_segments.return_value = _mini_segments()
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.side_effect = [
        "Alice spoke first.",
        LLMResponseError("Ollama response missing non-empty 'response' field"),
    ]

    with (
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.get_config",
            return_value=_cfg(),
        ),
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.build_ollama_analysis_client",
            return_value=mock_client,
        ),
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.write_llm_speaker_artifacts",
            return_value=("a.json", "a.md"),
        ),
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.write_llm_artifacts",
            return_value=("index.json", "index.md"),
        ),
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.create_output_service"
        ) as mock_os,
    ):
        mock_os.return_value.get_output_structure.return_value = SimpleNamespace(
            module_dir=str(tmp_path / "out" / "llm_speaker_summary")
        )
        mock_os.return_value.get_artifacts.return_value = []
        result = LLMSpeakerSummaryAnalysis().run_from_context(context)

    assert result["status"] == "success"
    speakers = result["payload"]["speakers"]
    statuses = {entry["speaker"]: entry["status"] for entry in speakers}
    assert statuses["Alice"] == "success"
    assert statuses["Bob"] == "failed"
    bob = next(entry for entry in speakers if entry["speaker"] == "Bob")
    assert bob["error_code"] == LLM_INVALID_RESPONSE
