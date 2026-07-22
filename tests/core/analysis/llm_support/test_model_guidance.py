"""Unit tests for Ollama model guidance matching."""

from __future__ import annotations

from transcriptx.core.analysis.llm_support.model_guidance import (
    guidance_for_model,
    infer_size_class,
    list_llm_model_guidance,
)


def test_infer_size_class_from_common_tags():
    assert infer_size_class("gemma3:1b") == "tiny"
    assert infer_size_class("llama3.2:3b") == "small"
    assert infer_size_class("qwen3:8b") == "mid"
    assert infer_size_class("qwen3.6:27b") == "large"
    assert infer_size_class("mistral:latest") == "unknown"


def test_qwen3_marked_json_unsafe():
    row = guidance_for_model("qwen3:8b")
    assert row.size_class == "mid"
    assert "json" in row.notes.lower() or "thinking" in row.notes.lower()
    assert "llm_summary" in row.best_for.lower()


def test_qwen36_discourages_json_modules():
    row = guidance_for_model("qwen3.6:27b")
    blob = f"{row.strengths} {row.best_for} {row.notes}".lower()
    assert "json" in blob
    assert "plain-text" in blob or "digest" in blob


def test_gemma_still_recommended_for_json():
    row = guidance_for_model("gemma3:12b")
    blob = f"{row.strengths} {row.best_for} {row.notes}".lower()
    assert "shared" in blob or "all modules" in blob
    assert "structured" in blob or "json" in blob or "default" in blob


def test_coder_models_discouraged_for_transcript_modules():
    row = guidance_for_model("qwen3-coder:30b")
    assert "not recommended" in row.best_for.lower()


def test_list_preserves_order_and_dedupes():
    rows = list_llm_model_guidance(
        ["qwen3:8b", " gemma3:12b ", "qwen3:8b", "", "llama3.2:3b"]
    )
    assert [r.model for r in rows] == ["qwen3:8b", "gemma3:12b", "llama3.2:3b"]


def test_unknown_family_uses_size_generic():
    row = guidance_for_model("mystery-model:7b")
    assert row.size_class == "mid"
    assert "balanced" in row.strengths.lower()
