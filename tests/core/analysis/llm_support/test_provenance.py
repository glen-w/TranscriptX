"""Provenance parity tests: field presence and shape."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.llm_support.provenance import (
    build_llm_provenance,
    json_generate_provenance_fields,
)


@pytest.mark.unit
def test_build_llm_provenance_full_shape() -> None:
    prov = build_llm_provenance(
        module_name="llm_summary",
        prompt_version="v1",
        provider="ollama",
        model="qwen3:8b",
        seed=42,
        temperature=0.0,
        max_output_tokens=2048,
        llm_request_sha256="req-hash",
        generation_options={"temperature": 0.0, "seed": 42},
        source_module="summary",
        source_result_sha256="src-hash",
        truncation={"truncated": True, "truncation_strategy": "head_tail"},
        model_digest="digest-abc",
    )
    assert sorted(prov.keys()) == [
        "generation_options",
        "llm_request_sha256",
        "max_output_tokens",
        "model",
        "model_digest",
        "module",
        "prompt_version",
        "provider",
        "seed",
        "source_module",
        "source_result_sha256",
        "temperature",
        "transcriptx_version",
        "truncated",
        "truncation_strategy",
    ]
    assert prov["module"] == "llm_summary"
    assert prov["source_module"] == "summary"
    assert prov["source_result_sha256"] == "src-hash"
    assert prov["model_digest"] == "digest-abc"
    assert prov["truncated"] is True
    assert prov["truncation_strategy"] == "head_tail"
    assert prov["generation_options"] == {"temperature": 0.0, "seed": 42}
    assert prov["max_output_tokens"] == 2048
    assert isinstance(prov["transcriptx_version"], str)


@pytest.mark.unit
def test_build_llm_provenance_minimal_omits_optionals() -> None:
    prov = build_llm_provenance(
        module_name="llm_summary",
        prompt_version="v1",
        provider="ollama",
        model="qwen3:8b",
        seed=42,
        temperature=0.0,
        max_output_tokens=None,
        llm_request_sha256="req-hash",
    )
    assert "source_module" not in prov
    assert "source_result_sha256" not in prov
    assert "model_digest" not in prov
    assert "truncated" not in prov
    assert prov["generation_options"] == {}
    assert prov["max_output_tokens"] is None


@pytest.mark.unit
def test_json_generate_provenance_fields_fallback(monkeypatch) -> None:
    from transcriptx.core.llm import json_with_fallback as fb

    monkeypatch.setattr(
        fb,
        "get_last_json_generate_outcome",
        lambda: fb.JsonGenerateOutcome(
            text="{}",
            model="gemma3:12b",
            used_fallback=True,
            preferred_failed=True,
        ),
    )
    model, source = json_generate_provenance_fields(
        model="qwen3.8:latest",
        model_selection_source="global",
    )
    assert model == "gemma3:12b"
    assert source == "fallback"

    prov = build_llm_provenance(
        module_name="narrative_summary",
        prompt_version="v1",
        provider="ollama",
        model="qwen3.8:latest",
        seed=1,
        temperature=0.0,
        max_output_tokens=64,
        llm_request_sha256="h",
        model_selection_source="global",
        apply_json_outcome=True,
    )
    assert prov["model"] == "gemma3:12b"
    assert prov["model_selection_source"] == "fallback"


@pytest.mark.unit
def test_json_generate_provenance_fields_no_outcome() -> None:
    from transcriptx.core.llm.json_with_fallback import reset_json_fallback_scope

    reset_json_fallback_scope()
    model, source = json_generate_provenance_fields(
        model="qwen3:8b",
        model_selection_source="global",
    )
    assert model == "qwen3:8b"
    assert source == "global"


@pytest.mark.unit
def test_json_consumers_apply_outcome_or_helper() -> None:
    """JSON LLM modules overlay producing-model provenance after generate."""
    from pathlib import Path

    root = Path("src/transcriptx/core/analysis")
    apply_outcome = (
        (root / "insights_narrative.py").read_text(encoding="utf-8"),
        (root / "narrative_summary.py").read_text(encoding="utf-8"),
        (root / "llm_action_items.py").read_text(encoding="utf-8"),
    )
    helper = (
        (root / "chart_descriptions/generate.py").read_text(encoding="utf-8"),
        (root / "group_llm_synthesis/synthesize.py").read_text(encoding="utf-8"),
        (root / "llm_custom_qa/analyze.py").read_text(encoding="utf-8"),
        (root / "llm_custom_qa/analyze_structured.py").read_text(encoding="utf-8"),
    )
    for src in apply_outcome:
        assert "apply_json_outcome=True" in src
    for src in helper:
        assert "json_generate_provenance_fields" in src
