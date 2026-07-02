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
from transcriptx.core.analysis.llm_summary_effort import LLMSummaryRuntime
from transcriptx.core.analysis.narrative_summary import NarrativeSummaryAnalysis
from transcriptx.core.llm.errors import (
    LLM_CONFIGURATION_ERROR,
    LLM_UNAVAILABLE,
    LLMConfigurationError,
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
            "transcriptx.core.analysis.llm_summary.build_llm_summary_ollama_client",
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
    prov = result["payload"]["provenance"]
    assert prov["input_truncated"] is False
    assert prov["input_coverage_ratio"] == 1.0
    assert prov["input_chars_total"] == prov["input_chars_used"]
    assert "input_chars" in prov


@pytest.mark.unit
def test_llm_summary_empty_transcript_error_code() -> None:
    context = MagicMock()
    context.transcript_path = "t.json"
    context.get_segments.return_value = [{"speaker": "A", "text": "  ", "start": 0}]
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    mock_client = MagicMock()
    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.build_llm_summary_ollama_client",
            return_value=mock_client,
        ),
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
    cfg.llm.provider = "ollama"
    mock_client = MagicMock()
    mock_client.generate.side_effect = LLMUnavailableError("down")
    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.build_llm_summary_ollama_client",
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
    cfg.llm.provider = "ollama"
    mock_client = MagicMock()
    mock_client.generate.return_value = "   "
    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.build_llm_summary_ollama_client",
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
    cfg.llm.default_temperature = 0.25

    effort_runtime = LLMSummaryRuntime(
        effort="low",
        profile_name="low",
        model="qwen3:8b",
        max_input_chars=400,
        request_timeout=60.0,
        max_output_tokens=1024,
    )

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.return_value = "Truncated summary."

    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.resolve_llm_summary_runtime",
            return_value=effort_runtime,
        ),
        patch(
            "transcriptx.core.analysis.llm_summary.build_llm_summary_ollama_client",
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
    assert prov["effort"] == "low"
    assert prov["effort_profile"] == "low"
    assert prov["request_timeout"] == 60.0
    assert prov["max_input_chars"] == 400
    assert prov["max_output_tokens"] == 1024
    assert prov["input_truncated"] is True
    assert prov["input_chars_total"] > prov["input_chars_used"]
    assert prov["input_coverage_ratio"] < 1.0
    assert "input_chars" in prov
    mock_client.generate.assert_called_once()
    sent_prompt = mock_client.generate.call_args.kwargs["prompt"]
    assert "<<<TRANSCRIPT>>>" in sent_prompt
    assert "<<<END TRANSCRIPT>>>" in sent_prompt
    assert len(sent_prompt) <= 400
    assert "Alice:" in sent_prompt


@pytest.mark.unit
def test_llm_summary_ignores_llm_cfg_max_input_chars_when_effort_active(
    tmp_path,
) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}
    context.get_segments.return_value = _mini_segments()

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    cfg.llm.max_input_chars = 999_999

    effort_runtime = LLMSummaryRuntime(
        effort="low",
        profile_name="low",
        model="qwen3:8b",
        max_input_chars=500,
        request_timeout=60.0,
        max_output_tokens=1024,
    )

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.return_value = "Summary."

    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.resolve_llm_summary_runtime",
            return_value=effort_runtime,
        ) as mock_resolve,
        patch(
            "transcriptx.core.analysis.llm_summary.build_llm_summary_ollama_client",
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

    mock_resolve.assert_called_once()
    prov = result["payload"]["provenance"]
    assert prov["max_input_chars"] == 500
    assert prov["input_chars"] <= 500


@pytest.mark.unit
def test_llm_summary_uses_effort_specific_client(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_segments.return_value = _mini_segments()
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    cfg.analysis.llm_summary.effort = "high"

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.return_value = "Summary."

    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.build_llm_summary_ollama_client",
            return_value=mock_client,
        ) as mock_build_client,
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
        LLMSummaryAnalysis().run_from_context(context)

    mock_build_client.assert_called_once()
    runtime = mock_build_client.call_args.kwargs["runtime"]
    assert runtime.effort == "high"


@pytest.mark.unit
def test_llm_summary_non_ollama_raises_configuration_error() -> None:
    context = MagicMock()
    context.transcript_path = "t.json"
    context.get_segments.return_value = _mini_segments()

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "openai"

    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.build_llm_summary_ollama_client",
        ) as mock_build_client,
        patch(
            "transcriptx.core.analysis.llm_summary.resolve_llm_summary_runtime",
        ) as mock_resolve,
    ):
        with pytest.raises(LLMConfigurationError) as exc:
            LLMSummaryAnalysis().run_from_context(context)

    mock_build_client.assert_not_called()
    mock_resolve.assert_not_called()
    assert exc.value.error_code == LLM_CONFIGURATION_ERROR


@pytest.mark.unit
def test_llm_summary_disabled_raises_configuration_error() -> None:
    context = MagicMock()
    context.transcript_path = "t.json"
    context.get_segments.return_value = _mini_segments()

    cfg = TranscriptXConfig()
    cfg.llm.enabled = False

    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.build_llm_summary_ollama_client",
        ) as mock_build_client,
        patch(
            "transcriptx.core.analysis.llm_summary.resolve_llm_summary_runtime",
        ) as mock_resolve,
    ):
        with pytest.raises(LLMConfigurationError) as exc:
            LLMSummaryAnalysis().run_from_context(context)

    mock_build_client.assert_not_called()
    mock_resolve.assert_not_called()
    assert exc.value.error_code == LLM_CONFIGURATION_ERROR


@pytest.mark.unit
def test_llm_summary_provenance_retains_input_chars_with_coverage_fields(
    tmp_path,
) -> None:
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
    mock_client.generate.return_value = "Summary."

    with (
        patch("transcriptx.core.analysis.llm_summary.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.llm_summary.build_llm_summary_ollama_client",
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
    assert isinstance(prov["input_chars"], int)
    assert prov["input_chars"] > prov["input_chars_used"]
    assert prov["input_chars_total"] == prov["input_chars_used"]
    assert prov["input_coverage_ratio"] == 1.0


@pytest.mark.unit
def test_narrative_summary_ignores_llm_summary_effort(tmp_path) -> None:
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
    cfg.analysis.llm_summary.effort = "max"

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
        ) as mock_get_client,
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
        NarrativeSummaryAnalysis().run_from_context(context)

    mock_get_client.assert_called_once()
