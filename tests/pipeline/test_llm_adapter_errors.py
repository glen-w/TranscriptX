"""Adapter-level tests for LLM typed error_code preservation."""

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
from transcriptx.core.llm.errors import (
    LLM_CONFIGURATION_ERROR,
    LLM_GENERATION_ERROR,
    LLM_INVALID_RESPONSE,
    LLM_MODEL_MISSING,
    LLM_TIMEOUT,
    LLM_UNAVAILABLE,
    LLMConfigurationError,
    LLMGenerationError,
    LLMModelMissingError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from transcriptx.core.pipeline.dag_execution_adapter import execute_single_module
from transcriptx.core.utils.config.main import TranscriptXConfig


def _pipeline() -> SimpleNamespace:
    return SimpleNamespace(
        logger=MagicMock(),
        _module_progress_heartbeat=lambda *_a, **_k: None,
    )


def _node(exc: Exception) -> SimpleNamespace:
    class _RaisingModule:
        def run_from_context(self, _context):
            raise exc

    return SimpleNamespace(
        function=_RaisingModule,
        description="LLM module",
        requirements=[],
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("exc", "expected_code"),
    [
        (ModuleEmptyInputError("empty"), LLM_EMPTY_INPUT),
        (ModuleDependencyMissingError("missing"), LLM_DEPENDENCY_MISSING),
        (LLMUnavailableError("down"), LLM_UNAVAILABLE),
        (LLMModelMissingError("missing model"), LLM_MODEL_MISSING),
        (LLMTimeoutError("timed out"), LLM_TIMEOUT),
        (LLMResponseError("bad json"), LLM_INVALID_RESPONSE),
        (LLMGenerationError("http fail"), LLM_GENERATION_ERROR),
        (LLMConfigurationError("bad config"), LLM_CONFIGURATION_ERROR),
    ],
)
def test_execute_single_module_preserves_typed_error_code(
    exc: Exception,
    expected_code: str,
) -> None:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        outcome = execute_single_module(
            _pipeline(),
            module_name="llm_summary",
            node=_node(exc),
            transcript_path="t.json",
            context=MagicMock(),
            requirements_resolver=None,
            named_speaker_count=2,
        )

    assert outcome.status == "failed"
    assert outcome.module_result is not None
    assert outcome.module_result["error"]["error_code"] == expected_code


@pytest.mark.unit
@pytest.mark.parametrize(
    ("exc", "expected_code"),
    [
        (ModuleEmptyInputError("empty"), LLM_EMPTY_INPUT),
        (
            ModuleDependencyMissingError(
                "missing", dependency="summary", state="missing"
            ),
            LLM_DEPENDENCY_MISSING,
        ),
        (LLMUnavailableError("down"), LLM_UNAVAILABLE),
        (LLMModelMissingError("missing model"), LLM_MODEL_MISSING),
        (LLMTimeoutError("timed out"), LLM_TIMEOUT),
        (LLMResponseError("bad json"), LLM_INVALID_RESPONSE),
        (LLMGenerationError("http fail"), LLM_GENERATION_ERROR),
        (LLMConfigurationError("bad config"), LLM_CONFIGURATION_ERROR),
    ],
)
def test_error_code_survives_to_canonical_outcomes(
    exc: Exception,
    expected_code: str,
    tmp_path,
) -> None:
    import json

    from transcriptx.core.pipeline.manifest_builder import build_run_results_summary
    from transcriptx.core.pipeline.manifest_loader import load_run_results
    from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        outcome = execute_single_module(
            _pipeline(),
            module_name="llm_summary",
            node=_node(exc),
            transcript_path="t.json",
            context=MagicMock(),
            requirements_resolver=None,
            named_speaker_count=2,
        )

    module_result = outcome.module_result
    assert outcome.status == "failed"
    assert module_result is not None
    payload = build_run_results_summary(
        run_id="run-1",
        transcript_key="mini",
        modules_enabled=["llm_summary"],
        modules_run=[],
        skipped_modules=[],
        errors=[f"llm_summary: {exc}"],
        module_results={"llm_summary": module_result},
    )
    path = tmp_path / "run_results.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_run_results(path)
    canonical = {row.module_id: row for row in project_canonical_outcomes(loaded)}
    assert canonical["llm_summary"].error_code == expected_code
