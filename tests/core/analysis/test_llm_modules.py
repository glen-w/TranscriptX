"""Tests for LLM analysis modules (mocked client)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.llm_module_errors import (
    LLM_DEPENDENCY_MISSING,
    LLM_EMPTY_INPUT,
    ModuleDependencyMissingError,
    ModuleEmptyInputError,
)
from transcriptx.core.analysis.llm_summary import LLMSummaryAnalysis
from transcriptx.core.analysis.narrative_summary import NarrativeSummaryAnalysis
from transcriptx.core.llm.errors import (
    LLM_UNAVAILABLE,
    LLMResponseError,
    LLMUnavailableError,
)
from transcriptx.core.utils.config.main import TranscriptXConfig


def _mini_segments() -> list[dict]:
    return [
        {"speaker": "Alice", "text": "Hello there.", "start": 0.0, "end": 1.0},
        {"speaker": "Bob", "text": "Hi Alice.", "start": 1.0, "end": 2.0},
    ]


def _summary_payload() -> dict:
    return {
        "overview": {"paragraph": "Alice and Bob greeted each other."},
        "key_themes": {"bullets": [{"text": "Greetings"}]},
        "tension_points": {"bullets": []},
        "commitments": {"items": []},
    }


@pytest.mark.unit
def test_narrative_summary_success(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_segments.return_value = _mini_segments()
    context.get_base_name.return_value = "mini"
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}
    context.get_analysis_result.return_value = _summary_payload()

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.return_value = (
        '{"narrative": "Alice and Bob exchanged greetings."}'
    )

    with (
        patch(
            "transcriptx.core.analysis.narrative_summary.get_config", return_value=cfg
        ),
        patch(
            "transcriptx.core.analysis.narrative_summary.get_llm_client",
            return_value=mock_client,
        ),
        patch(
            "transcriptx.core.analysis.narrative_summary.write_llm_artifacts",
            return_value=("a.json", "a.md"),
        ),
        patch(
            "transcriptx.core.analysis.narrative_summary.create_output_service"
        ) as mock_os,
    ):
        mock_os.return_value.get_output_structure.return_value = SimpleNamespace(
            module_dir=str(tmp_path / "out" / "narrative_summary")
        )
        mock_os.return_value.get_artifacts.return_value = []
        result = NarrativeSummaryAnalysis().run_from_context(context)

    assert result["status"] == "success"
    assert "Alice and Bob" in result["payload"]["narrative"]
    mock_client.generate.assert_called_once()


@pytest.mark.unit
def test_narrative_summary_empty_signal_error_code() -> None:
    context = MagicMock()
    context.transcript_path = "t.json"
    context.get_analysis_result.return_value = {
        "overview": {},
        "key_themes": {"bullets": []},
        "tension_points": {"bullets": []},
        "commitments": {"items": []},
    }
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    with (
        patch(
            "transcriptx.core.analysis.narrative_summary.get_config", return_value=cfg
        ),
        patch("transcriptx.core.analysis.narrative_summary.get_llm_client"),
    ):
        with pytest.raises(ModuleEmptyInputError) as exc:
            NarrativeSummaryAnalysis().run_from_context(context)
    assert exc.value.error_code == LLM_EMPTY_INPUT


@pytest.mark.unit
def test_narrative_summary_missing_dependency_error_code() -> None:
    context = MagicMock()
    context.transcript_path = "t.json"
    context.get_base_name.return_value = "mini"
    context.get_transcript_dir.return_value = "/nonexistent/out"
    context.get_analysis_result.return_value = None
    cfg = TranscriptXConfig()
    with patch(
        "transcriptx.core.analysis.narrative_summary.get_config", return_value=cfg
    ):
        with pytest.raises(ModuleDependencyMissingError) as exc:
            NarrativeSummaryAnalysis().run_from_context(context)
    assert exc.value.error_code == LLM_DEPENDENCY_MISSING


@pytest.mark.unit
def test_llm_summary_success(tmp_path) -> None:
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
    mock_client.generate.return_value = "A short meeting greeting."

    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.get_llm_client",
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
    assert result["payload"]["summary"] == "A short meeting greeting."


@pytest.mark.unit
def test_llm_summary_empty_transcript_error_code() -> None:
    context = MagicMock()
    context.transcript_path = "t.json"
    context.get_segments.return_value = [{"speaker": "A", "text": "  ", "start": 0}]
    cfg = TranscriptXConfig()
    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch("transcriptx.core.analysis.llm_summary.get_llm_client"),
    ):
        with pytest.raises(ModuleEmptyInputError) as exc:
            LLMSummaryAnalysis().run_from_context(context)
    assert exc.value.error_code == LLM_EMPTY_INPUT


@pytest.mark.unit
def test_llm_summary_generation_failure_error_code() -> None:
    context = MagicMock()
    context.transcript_path = "t.json"
    context.get_segments.return_value = _mini_segments()
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    mock_client = MagicMock()
    mock_client.generate.side_effect = LLMUnavailableError("down")
    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.get_llm_client",
            return_value=mock_client,
        ),
    ):
        with pytest.raises(LLMUnavailableError) as exc:
            LLMSummaryAnalysis().run_from_context(context)
    assert exc.value.error_code == LLM_UNAVAILABLE


@pytest.mark.unit
def test_narrative_summary_failed_summary_dependency(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = "t.json"
    context.get_analysis_result.return_value = {"status": "error", "payload": {}}
    cfg = TranscriptXConfig()
    with patch(
        "transcriptx.core.analysis.narrative_summary.get_config", return_value=cfg
    ):
        with pytest.raises(ModuleDependencyMissingError) as exc:
            NarrativeSummaryAnalysis().run_from_context(context)
    assert exc.value.error_code == LLM_DEPENDENCY_MISSING


@pytest.mark.unit
def test_narrative_summary_provenance_fields(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_base_name.return_value = "mini"
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}
    context.get_analysis_result.return_value = _summary_payload()

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    cfg.llm.seed = 42

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.return_value = '{"narrative": "Done."}'

    with (
        patch(
            "transcriptx.core.analysis.narrative_summary.get_config", return_value=cfg
        ),
        patch(
            "transcriptx.core.analysis.narrative_summary.get_llm_client",
            return_value=mock_client,
        ),
        patch(
            "transcriptx.core.analysis.narrative_summary.write_llm_artifacts",
            return_value=("a.json", "a.md"),
        ),
        patch(
            "transcriptx.core.analysis.narrative_summary.create_output_service"
        ) as mock_os,
    ):
        mock_os.return_value.get_output_structure.return_value = SimpleNamespace(
            module_dir=str(tmp_path / "out" / "narrative_summary")
        )
        mock_os.return_value.get_artifacts.return_value = []
        result = NarrativeSummaryAnalysis().run_from_context(context)

    prov = result["payload"]["provenance"]
    assert prov["source_module"] == "summary"
    assert prov["source_result_sha256"]
    assert prov["llm_request_sha256"]
    assert prov["generation_options"]["num_predict"] is not None
    assert prov["temperature"] == 0.0
    assert prov["seed"] == 42
    assert result["payload"]["schema_id"] == "transcriptx.narrative_summary.v1"


@pytest.mark.unit
def test_llm_summary_empty_model_response_error_code() -> None:
    context = MagicMock()
    context.transcript_path = "t.json"
    context.get_segments.return_value = _mini_segments()
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    mock_client = MagicMock()
    mock_client.generate.return_value = "   "
    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.get_llm_client",
            return_value=mock_client,
        ),
    ):
        with pytest.raises(LLMResponseError):
            LLMSummaryAnalysis().run_from_context(context)


@pytest.mark.unit
def test_llm_summary_provenance_includes_truncation_metadata(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}
    long_segments = [
        {
            "speaker": "Alice",
            "text": "word " * 80,
            "start": float(i),
            "end": float(i + 1),
        }
        for i in range(40)
    ]
    context.get_segments.return_value = long_segments

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    cfg.llm.max_input_chars = 400
    cfg.llm.default_temperature = 0.25

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.return_value = "Truncated summary."

    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.get_llm_client",
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

    prov = result["payload"]["provenance"]
    assert prov["truncated"] is True
    assert prov["llm_request_sha256"]
    assert prov["input_chars"] <= 400
    assert prov["total_segments"] == 40
    assert prov["generation_options"]["num_predict"] is not None
    mock_client.generate.assert_called_once()
    sent_prompt = mock_client.generate.call_args.kwargs["prompt"]
    assert "<<<TRANSCRIPT>>>" in sent_prompt
    assert "<<<END TRANSCRIPT>>>" in sent_prompt
    assert len(sent_prompt) <= 400
    assert "Alice:" in sent_prompt
