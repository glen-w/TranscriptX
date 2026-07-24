"""Unit tests for Ollama model guidance matching and metadata enrichment."""

from __future__ import annotations

from transcriptx.core.analysis.llm_support.model_guidance import (
    LibraryMeta,
    format_context_window,
    format_disk_size,
    format_parameter_size,
    guidance_for_model,
    infer_size_class,
    list_llm_model_guidance,
    parse_library_html_meta,
    producer_for_model,
    released_for_model,
)
from transcriptx.core.llm.ollama_client import OllamaModelInfo


def test_infer_size_class_from_common_tags():
    assert infer_size_class("gemma3:1b") == "tiny"
    assert infer_size_class("llama3.2:3b") == "small"
    assert infer_size_class("qwen3:8b") == "mid"
    assert infer_size_class("qwen3.6:27b") == "large"
    assert infer_size_class("mistral:latest") == "unknown"


def test_infer_size_class_from_parameter_size_when_tag_lacks_size():
    assert infer_size_class("mistral:latest", parameter_size="7.2B") == "mid"
    assert infer_size_class("phi4:latest", parameter_size="14.7B") == "large"
    assert infer_size_class("gemma3:latest", parameter_size="999.89M") == "tiny"


def test_format_helpers():
    assert format_parameter_size("12.2B") == "12.2B"
    assert format_parameter_size("7.2B") == "7.2B"
    assert format_parameter_size("8.0B") == "8B"
    assert format_parameter_size("999.89M") == "1B"
    assert format_context_window(131072) == "128K"
    assert format_context_window(32768) == "32K"
    assert format_context_window(1_024_000) == "1M"
    assert format_disk_size(4_400_000_000) == "4.1 GB"


def test_producer_and_release_catalog():
    assert producer_for_model("gemma3:12b") == "Google"
    assert producer_for_model("mistral:latest") == "Mistral AI"
    assert producer_for_model("mystery:7b", family="cohere2") == "Cohere"
    assert released_for_model("gemma3:12b") == "Mar 2025"
    assert released_for_model("gpt-oss:20b") == "Aug 2025"


def test_guidance_enriches_from_ollama_info():
    info = OllamaModelInfo(
        name="mistral:latest",
        size_bytes=4_371_968_000,
        family="llama",
        parameter_size="7.2B",
        context_length=32768,
    )
    row = guidance_for_model("mistral:latest", info=info)
    assert row.size_class == "mid"
    assert row.parameters == "7.2B"
    assert row.context_window == "32K"
    assert row.producer == "Mistral AI"
    assert row.released == "Sep 2023"
    assert row.disk_size is not None


def test_list_fills_unknown_class_from_ollama_parameter_size():
    """Tags like ``:latest`` get size class + params from live Ollama metadata."""
    infos = [
        OllamaModelInfo(
            name="mistral:latest",
            parameter_size="7.2B",
            context_length=32768,
            size_bytes=4_400_000_000,
            family="llama",
        )
    ]
    rows = list_llm_model_guidance(["mistral:latest"], infos=infos)
    assert len(rows) == 1
    row = rows[0]
    assert row.size_class == "mid"
    assert row.parameters == "7.2B"
    assert row.context_window == "32K"
    assert row.disk_size is not None


def test_list_library_fetcher_fills_unknown_producer_once_per_base():
    """Unknown families can soft-pull producer from a library fetcher (cached by base)."""
    calls: list[str] = []

    def _fetch(tag: str) -> LibraryMeta:
        calls.append(tag)
        return LibraryMeta(producer="Acme Labs", released="Feb 2026")

    rows = list_llm_model_guidance(
        ["mystery-a:7b", "mystery-a:latest", "mystery-b:3b"],
        library_fetcher=_fetch,
    )
    assert [r.producer for r in rows] == ["Acme Labs", "Acme Labs", "Acme Labs"]
    assert [r.released for r in rows] == ["Feb 2026", "Feb 2026", "Feb 2026"]
    # One fetch per model base name, not per tag.
    assert calls == ["mystery-a:7b", "mystery-b:3b"]


def test_list_library_meta_map_used_without_fetcher():
    rows = list_llm_model_guidance(
        ["obscure-model:4b"],
        library_meta_by_base={
            "obscure-model": LibraryMeta(producer="From Map", released="Jun 2024"),
        },
    )
    assert rows[0].producer == "From Map"
    assert rows[0].released == "Jun 2024"


def test_fetch_ollama_library_meta_soft_fails(monkeypatch):
    from transcriptx.core.analysis.llm_support import model_guidance as mg

    def _boom(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(mg, "urlopen", _boom)
    assert mg.fetch_ollama_library_meta("mistral") is None


def test_library_meta_overrides_producer():
    row = guidance_for_model(
        "mystery-model:7b",
        library_meta=LibraryMeta(producer="Acme Labs", released="Jan 2026"),
    )
    assert row.producer == "Acme Labs"
    assert row.released == "Jan 2026"


def test_parse_library_html_meta_extracts_producer():
    html = (
        '<meta name="description" content="The 7B model released by '
        'Mistral AI, updated to version 0.3."/>'
    )
    meta = parse_library_html_meta(html)
    assert meta is not None
    assert meta.producer == "Mistral AI"


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


def test_gemma3_4b_small_caption_guidance():
    row = guidance_for_model("gemma3:4b")
    assert row.size_class == "small"
    assert "chart_descriptions" in row.best_for.lower()
    assert "llm_action_items" in row.notes.lower()


def test_llama32_3b_discourages_action_items():
    row = guidance_for_model("llama3.2:3b")
    assert row.size_class == "small"
    blob = f"{row.best_for} {row.notes}".lower()
    assert "llm_action_items" in blob
    assert "not" in blob or "schema" in blob or "empty" in blob


def test_mistral_nemo_long_context_guidance():
    row = guidance_for_model("mistral-nemo:latest")
    assert "long" in row.strengths.lower() or "context" in row.strengths.lower()
    assert "llm_summary" in row.best_for.lower()
