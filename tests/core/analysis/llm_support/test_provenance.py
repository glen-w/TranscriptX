"""Provenance parity tests: field presence and shape."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.llm_support.provenance import build_llm_provenance


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
