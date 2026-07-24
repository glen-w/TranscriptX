"""Unit tests for thinking-model heuristics and JSON-consumer filtering."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from transcriptx.core.analysis.llm_support.model_selection import LlmModelSelection
from transcriptx.core.llm.thinking_models import (
    LLM_JSON_FORMAT_CONSUMER_IDS,
    filter_models_for_json_consumers,
    is_thinking_model,
    selection_uses_thinking_for_json,
)
from transcriptx.web.components.llm_model_selector import (
    _options_for_consumer,
    _selected_json_consumers,
    launch_gate_reasons,
)


@pytest.mark.unit
def test_is_thinking_model_markers() -> None:
    assert is_thinking_model("qwen3:8b") is True
    assert is_thinking_model("qwen3.6:27b") is True
    assert is_thinking_model("qwen3-coder:30b") is True
    assert is_thinking_model("deepseek-r1:8b") is True
    assert is_thinking_model("gpt-oss:20b") is True
    assert is_thinking_model("llama3.2:3b") is False
    assert is_thinking_model("gemma3:12b") is False
    assert is_thinking_model("qwen2.5:7b") is False
    assert is_thinking_model("") is False
    assert is_thinking_model(None) is False


@pytest.mark.unit
def test_filter_models_for_json_consumers() -> None:
    installed = (
        "gemma3:12b",
        "qwen3.6:27b",
        "qwen2.5:7b",
        "deepseek-r1:8b",
    )
    assert filter_models_for_json_consumers(installed) == (
        "gemma3:12b",
        "qwen2.5:7b",
    )
    assert (
        filter_models_for_json_consumers(installed, include_thinking=True) == installed
    )


@pytest.mark.unit
def test_options_hide_thinking_for_shared_when_json_selected() -> None:
    installed = ["gemma3:12b", "qwen3.6:27b", "llama3.2:3b"]
    shared = _options_for_consumer(
        installed,
        consumer_id=None,
        json_consumers_selected=["chart_descriptions"],
    )
    assert "qwen3.6:27b" not in shared
    assert "gemma3:12b" in shared

    plain_only = _options_for_consumer(
        installed,
        consumer_id=None,
        json_consumers_selected=[],
    )
    assert "qwen3.6:27b" in plain_only


@pytest.mark.unit
def test_options_hide_thinking_on_json_module_rows() -> None:
    installed = ["gemma3:12b", "qwen3:8b"]
    json_row = _options_for_consumer(
        installed,
        consumer_id="llm_action_items",
        json_consumers_selected=[],
    )
    plain_row = _options_for_consumer(
        installed,
        consumer_id="llm_summary",
        json_consumers_selected=[],
    )
    assert "qwen3:8b" not in json_row
    assert "qwen3:8b" in plain_row


@pytest.mark.unit
def test_launch_gate_blocks_thinking_shared_for_json_modules() -> None:
    with patch(
        "transcriptx.core.pipeline.module_registry.get_module_info",
        return_value=SimpleNamespace(requires_llm=True),
    ):
        reasons = launch_gate_reasons(
            selection=LlmModelSelection(mode="shared", shared_model="qwen3.6:27b"),
            selected_modules=["chart_descriptions", "llm_summary"],
            installed=("qwen3.6:27b", "gemma3:12b"),
            list_error=None,
            include_group=False,
            llm_enabled=True,
            provider="ollama",
        )
    assert any("Thinking-family" in r for r in reasons)
    assert any("chart_descriptions" in r for r in reasons)


@pytest.mark.unit
def test_launch_gate_allows_thinking_for_plain_text_only() -> None:
    with patch(
        "transcriptx.core.pipeline.module_registry.get_module_info",
        return_value=SimpleNamespace(requires_llm=True),
    ):
        reasons = launch_gate_reasons(
            selection=LlmModelSelection(mode="shared", shared_model="qwen3.6:27b"),
            selected_modules=["llm_summary"],
            installed=("qwen3.6:27b", "gemma3:12b"),
            list_error=None,
            include_group=False,
            llm_enabled=True,
            provider="ollama",
        )
    assert not any("Thinking-family" in r for r in reasons)


@pytest.mark.unit
def test_selected_json_consumers_and_selection_helper() -> None:
    assert "chart_descriptions" in LLM_JSON_FORMAT_CONSUMER_IDS
    consumers = _selected_json_consumers(
        ["llm_summary", "chart_descriptions"], include_group=False
    )
    assert consumers == ["chart_descriptions"]
    flagged = selection_uses_thinking_for_json(
        mode="per_module",
        shared_model=None,
        module_models={
            "chart_descriptions": "qwen3:8b",
            "llm_summary": "qwen3:8b",
        },
        json_consumer_ids=consumers,
    )
    assert flagged == ["chart_descriptions"]
