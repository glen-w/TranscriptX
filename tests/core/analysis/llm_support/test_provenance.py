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
    assert "base_url" not in prov


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
    assert "base_url" not in prov


@pytest.mark.unit
def test_redact_llm_base_url_drops_userinfo_path_and_query() -> None:
    from transcriptx.core.analysis.llm_support.provenance import redact_llm_base_url

    assert (
        redact_llm_base_url("https://user:secret@api.example.com:8443/v1/chat?x=1")
        == "https://api.example.com:8443"
    )
    assert redact_llm_base_url("http://127.0.0.1:4000/v1") == "http://127.0.0.1:4000"
    assert redact_llm_base_url("") == ""
    assert redact_llm_base_url("not a url") == ""


@pytest.mark.unit
def test_openai_compatible_provenance_persists_redacted_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prov = build_llm_provenance(
        module_name="llm_summary",
        prompt_version="v1",
        provider="openai_compatible",
        model="gpt-4o-mini",
        seed=1,
        temperature=0.0,
        max_output_tokens=16,
        llm_request_sha256="req",
        base_url="https://user:key@api.example.com/v1?token=abc",
    )
    assert prov["base_url"] == "https://api.example.com"
    assert "user" not in prov["base_url"]
    assert "secret" not in str(prov)
    assert "token=" not in str(prov)

    monkeypatch.delenv("TRANSCRIPTX_LLM_API_KEY", raising=False)

    from_config = build_llm_provenance(
        module_name="llm_summary",
        prompt_version="v1",
        provider="openai_compatible",
        model="m",
        seed=1,
        temperature=0.0,
        max_output_tokens=None,
        llm_request_sha256="req",
        base_url=None,
    )
    # Live config may be empty in tests; if present it is still redacted.
    if "base_url" in from_config:
        assert "://" in from_config["base_url"]
        assert "@" not in from_config["base_url"]
        assert "?" not in from_config["base_url"]
