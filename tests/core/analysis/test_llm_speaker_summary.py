"""Tests for llm_speaker_summary analysis module (mocked client)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.llm_support.speakers import (
    collect_named_speaker_groups_for_llm,
)
from transcriptx.core.analysis.llm_module_errors import (
    LLM_EMPTY_INPUT,
    ModuleEmptyInputError,
)
from transcriptx.core.analysis.llm_speaker_summary import LLMSpeakerSummaryAnalysis
from transcriptx.core.llm.errors import LLM_INVALID_RESPONSE, LLMResponseError
from transcriptx.core.utils.config.main import TranscriptXConfig


def _mini_segments() -> list[dict]:
    return [
        {"speaker": "Alice", "text": "Hello there.", "start": 0.0, "end": 1.0},
        {"speaker": "Bob", "text": "Hi Alice.", "start": 1.0, "end": 2.0},
        {"speaker": "SPEAKER_02", "text": "Unmapped line.", "start": 2.0, "end": 3.0},
    ]


@pytest.mark.unit
def test_collect_named_speaker_groups_filters_unnamed() -> None:
    groups = collect_named_speaker_groups_for_llm(
        _mini_segments(),
        runtime_flags={},
    )
    names = {g["display_name"] for g in groups}
    assert names == {"Alice", "Bob"}


@pytest.mark.unit
def test_collect_named_speaker_groups_respects_ignored_ids() -> None:
    groups = collect_named_speaker_groups_for_llm(
        _mini_segments(),
        runtime_flags={"ignored_speaker_ids": {"Bob"}},
    )
    names = {g["display_name"] for g in groups}
    assert names == {"Alice"}


@pytest.mark.unit
def test_llm_speaker_summary_success(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_segments.return_value = _mini_segments()
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.side_effect = [
        "Alice spoke first.",
        "Bob replied briefly.",
    ]

    with (
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.get_config",
            return_value=cfg,
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
    assert result["payload"]["provenance"]["success_count"] == 2
    assert len(result["payload"]["speakers"]) == 2
    assert mock_client.generate.call_count == 2


@pytest.mark.unit
def test_llm_speaker_summary_empty_input_error_code() -> None:
    context = MagicMock()
    context.transcript_path = "t.json"
    context.get_segments.return_value = [
        {"speaker": "SPEAKER_00", "text": "Only diarized.", "start": 0.0, "end": 1.0}
    ]
    context.get_runtime_flags.return_value = {}
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    mock_client = MagicMock()
    with (
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.get_config",
            return_value=cfg,
        ),
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.build_ollama_analysis_client",
            return_value=mock_client,
        ),
    ):
        with pytest.raises(ModuleEmptyInputError) as exc:
            LLMSpeakerSummaryAnalysis().run_from_context(context)
    assert exc.value.error_code == LLM_EMPTY_INPUT


@pytest.mark.unit
def test_llm_speaker_summary_partial_success_when_one_speaker_fails(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_segments.return_value = _mini_segments()
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.side_effect = [
        "Alice spoke first.",
        LLMResponseError("LLM returned an empty summary"),
    ]

    with (
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.get_config",
            return_value=cfg,
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
    assert speakers[1]["error_code"] == LLM_INVALID_RESPONSE


@pytest.mark.unit
def test_llm_speaker_summary_all_failed_raises_invalid_response(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_segments.return_value = [
        {"speaker": "Alice", "text": "Hello.", "start": 0.0, "end": 1.0},
    ]
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.return_value = "   "

    with (
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.get_config",
            return_value=cfg,
        ),
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.build_ollama_analysis_client",
            return_value=mock_client,
        ),
        patch(
            "transcriptx.core.analysis.llm_speaker_summary.create_output_service"
        ) as mock_os,
    ):
        mock_os.return_value.get_output_structure.return_value = SimpleNamespace(
            module_dir=str(tmp_path / "out" / "llm_speaker_summary")
        )
        with pytest.raises(LLMResponseError) as exc:
            LLMSpeakerSummaryAnalysis().run_from_context(context)
    assert exc.value.error_code == LLM_INVALID_RESPONSE
