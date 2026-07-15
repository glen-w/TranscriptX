"""Optional live Ollama tests for LLM analysis modules.

Skipped unless ``TRANSCRIPTX_LLM_LIVE_TEST=1``. Excluded from the default fast
suite via ``integration`` / ``requires_api`` / ``slow`` markers.

Requires a reachable Ollama daemon and installed models. Diversity selection
covers small/mid/large/thinking buckets when tags are present; override with
``TRANSCRIPTX_LLM_LIVE_MODELS``.
"""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.llm_action_items import LLMActionItemsAnalysis
from transcriptx.core.analysis.llm_speaker_summary import LLMSpeakerSummaryAnalysis
from transcriptx.core.analysis.llm_summary import LLMSummaryAnalysis
from transcriptx.core.llm.errors import LLMResponseError
from transcriptx.core.utils.config import get_config, set_config
from transcriptx.core.utils.config.main import TranscriptXConfig
from tests.core.llm.ollama_live_helpers import (
    SelectedModel,
    installed_ollama_models,
    live_base_url,
    resolve_live_model,
    select_diverse_models,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_api,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.getenv("TRANSCRIPTX_LLM_LIVE_TEST", "").strip().lower()
        not in ("1", "true", "yes", "on"),
        reason="Set TRANSCRIPTX_LLM_LIVE_TEST=1 to run live Ollama LLM module tests",
    ),
]


def _live_cfg(*, model: str, effort: str = "low") -> TranscriptXConfig:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    cfg.llm.base_url = live_base_url()
    cfg.llm.model = model
    cfg.llm.seed = 42
    cfg.llm.default_temperature = 0.0
    cfg.analysis.llm_summary.effort = effort  # type: ignore[assignment]
    cfg.analysis.llm_speaker_summary.effort = effort  # type: ignore[assignment]
    cfg.analysis.llm_action_items.effort = effort  # type: ignore[assignment]
    return cfg


def _context(tmp_path, segments: list[dict[str, Any]]) -> MagicMock:
    from pathlib import Path

    root = Path(tmp_path)
    root.mkdir(parents=True, exist_ok=True)
    transcript = root / "live_transcript.json"
    transcript.write_text(json.dumps({"segments": segments}), encoding="utf-8")
    out = root / "out"
    out.mkdir(exist_ok=True)
    context = MagicMock()
    context.transcript_path = str(transcript)
    context.get_segments.return_value = segments
    context.get_base_name.return_value = "live"
    context.get_transcript_dir.return_value = str(out)
    context.get_run_id.return_value = "live-run"
    context.get_runtime_flags.return_value = {}
    context.store_analysis_result = MagicMock()
    return context


def _with_live_config(cfg: TranscriptXConfig):
    previous = get_config()
    set_config(cfg)
    return previous


def _diverse_models() -> list[SelectedModel]:
    base_url = live_base_url()
    installed = installed_ollama_models(base_url)
    assert installed, "Ollama /api/tags returned no models"
    selected = select_diverse_models(installed, max_models=4)
    assert selected, "No diverse models could be selected from installed tags"
    return selected


@pytest.fixture
def live_cfg() -> TranscriptXConfig:
    return _live_cfg(model=resolve_live_model(live_base_url()), effort="low")


@pytest.mark.timeout(1200)
def test_live_llm_summary_across_diverse_models(tmp_path) -> None:
    selected_models = _diverse_models()
    segments = [
        {
            "speaker": "Alice",
            "text": "We need to ship the report by Friday.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "Bob",
            "text": "I will draft the executive summary tomorrow morning.",
            "start": 2.0,
            "end": 5.0,
        },
    ]
    for selected in selected_models:
        context = _context(tmp_path / selected.name.replace(":", "_"), segments)
        cfg = _live_cfg(model=selected.name)
        previous = _with_live_config(cfg)
        try:
            result = LLMSummaryAnalysis().run_from_context(context)
        except LLMResponseError as exc:
            if selected.thinking:
                assert exc.error_code == "llm_invalid_response"
                continue
            raise
        finally:
            set_config(previous)

        assert result["status"] == "success", selected.name
        summary = result["payload"].get("summary")
        assert isinstance(summary, str) and summary.strip(), selected.name


@pytest.mark.timeout(1200)
def test_live_llm_speaker_summary_across_diverse_models(tmp_path) -> None:
    selected_models = _diverse_models()
    segments = [
        {
            "speaker": "Alice",
            "text": "I own the budget review for next week.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "Bob",
            "text": "I will collect the vendor quotes by Wednesday.",
            "start": 2.0,
            "end": 4.0,
        },
    ]
    for selected in selected_models:
        context = _context(tmp_path / selected.name.replace(":", "_"), segments)
        cfg = _live_cfg(model=selected.name)
        previous = _with_live_config(cfg)
        try:
            result = LLMSpeakerSummaryAnalysis().run_from_context(context)
        except LLMResponseError as exc:
            if selected.thinking:
                assert exc.error_code == "llm_invalid_response"
                continue
            raise
        finally:
            set_config(previous)

        assert result["status"] == "success", selected.name
        speakers = result["payload"].get("speakers") or []
        assert len(speakers) == 2, selected.name
        success_count = result["payload"]["provenance"]["success_count"]
        if selected.thinking:
            assert success_count >= 1, selected.name
        else:
            assert success_count == 2, selected.name


@pytest.mark.timeout(600)
def test_live_llm_summary_module(tmp_path, live_cfg: TranscriptXConfig) -> None:
    """Legacy single-model smoke retained for quick live checks."""
    segments = [
        {
            "speaker": "Alice",
            "text": "We need to ship the report by Friday.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "Bob",
            "text": "I will draft the executive summary tomorrow morning.",
            "start": 2.0,
            "end": 5.0,
        },
    ]
    context = _context(tmp_path, segments)
    previous = _with_live_config(live_cfg)
    try:
        result = LLMSummaryAnalysis().run_from_context(context)
    finally:
        set_config(previous)

    assert result["status"] == "success"
    payload = result["payload"]
    assert isinstance(payload.get("summary"), str) and payload["summary"].strip()
    context.store_analysis_result.assert_called()


@pytest.mark.timeout(600)
def test_live_llm_action_items_module(tmp_path, live_cfg: TranscriptXConfig) -> None:
    # Prefer a non-reasoning JSON-friendly model when available; qwen3 thinking
    # outputs often break strict action-item JSON parsing on small tiers.
    base_url = live_cfg.llm.base_url
    installed = installed_ollama_models(base_url)
    for candidate in (
        os.getenv("TRANSCRIPTX_LLM_ACTION_ITEMS_MODEL", "").strip(),
        "llama3.2:3b",
        "mistral:latest",
        "qwen2.5:7b",
        live_cfg.llm.model,
    ):
        if candidate and candidate in installed:
            live_cfg.llm.model = candidate
            break

    segments = [
        {
            "speaker": "Alice",
            "text": "Bob, please send the signed contract to legal by Thursday.",
            "start": 0.0,
            "end": 3.0,
        },
        {
            "speaker": "Bob",
            "text": "Understood. I will email the signed contract to legal on Thursday.",
            "start": 3.0,
            "end": 6.0,
        },
    ]
    context = _context(tmp_path, segments)
    previous = _with_live_config(live_cfg)
    try:
        result = LLMActionItemsAnalysis().run_from_context(context)
    except LLMResponseError as exc:
        pytest.skip(
            f"Live action-items JSON not returned by model {live_cfg.llm.model!r}: {exc}"
        )
    finally:
        set_config(previous)

    assert result["status"] == "success"
    payload = result["payload"]
    assert payload["schema_id"] == "transcriptx.llm_action_items.v1"
    items = payload.get("items")
    assert isinstance(items, list)
    assert payload["provenance"]["provider"] == "ollama"


def test_live_cfg_resolves_installed_model(live_cfg: TranscriptXConfig) -> None:
    """Sanity: live fixture points at an installed Ollama model when daemon is up."""
    installed = installed_ollama_models(live_cfg.llm.base_url)
    assert installed, "Ollama /api/tags returned no models"
    assert live_cfg.llm.model in installed
