"""Unit tests for live Ollama diversity helpers."""

from __future__ import annotations

import pytest

from tests.core.llm.ollama_live_helpers import (
    is_thinking_model,
    select_diverse_models,
)


@pytest.mark.unit
def test_is_thinking_model_markers() -> None:
    assert is_thinking_model("qwen3:8b") is True
    assert is_thinking_model("deepseek-r1:8b") is True
    assert is_thinking_model("gpt-oss:20b") is True
    assert is_thinking_model("llama3.2:3b") is False
    assert is_thinking_model("gemma3:12b") is False
    assert is_thinking_model("qwen2.5:7b") is False


@pytest.mark.unit
def test_select_diverse_models_picks_one_per_bucket() -> None:
    installed = [
        "llama3.2:3b",
        "gemma3:12b",
        "qwen2.5:7b",
        "qwen3.6:27b",
        "qwen3:8b",
        "deepseek-r1:8b",
    ]
    selected = select_diverse_models(installed, max_models=4)
    names = [row.name for row in selected]
    assert "gemma3:12b" in names  # preferred mid regression host
    assert "llama3.2:3b" in names
    assert len(selected) == 4
    buckets = [row.bucket for row in selected]
    assert len(buckets) == len(set(buckets))


@pytest.mark.unit
def test_select_diverse_models_force_override() -> None:
    installed = ["llama3.2:3b", "gemma3:12b", "qwen3:8b"]
    selected = select_diverse_models(installed, force=["qwen3:8b", "llama3.2:3b"])
    assert [row.name for row in selected] == ["qwen3:8b", "llama3.2:3b"]
    assert selected[0].thinking is True


@pytest.mark.unit
def test_select_diverse_models_force_missing_raises() -> None:
    with pytest.raises(AssertionError, match="not installed"):
        select_diverse_models(["llama3.2:3b"], force=["missing:1b"])
