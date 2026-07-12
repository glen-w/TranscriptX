"""Unit tests for llm_summary effort profile resolution."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from transcriptx.core.analysis.llm_summary_effort import (
    BUILTIN_LLM_SUMMARY_EFFORT_PROFILES,
    LLMSummaryEffortProfile,
    LLMSummaryRuntime,
    build_llm_summary_ollama_client,
    require_llm_summary_ollama,
    resolve_llm_summary_runtime,
)
from transcriptx.core.llm import DEFAULT_OLLAMA_MODEL
from transcriptx.core.llm.errors import LLM_CONFIGURATION_ERROR, LLMConfigurationError
from transcriptx.core.utils.config.system import LLMConfig


def _llm_cfg(**overrides: object) -> LLMConfig:
    cfg = LLMConfig(enabled=True, provider="ollama", model="custom-model:7b")
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


@pytest.mark.unit
def test_medium_profile_is_completeness_oriented() -> None:
    profile = BUILTIN_LLM_SUMMARY_EFFORT_PROFILES["medium"]
    assert profile.max_input_chars == 128_000
    assert profile.request_timeout == 1350.0
    assert profile.max_output_tokens == 4096


@pytest.mark.unit
@pytest.mark.parametrize(
    ("effort", "max_input_chars", "request_timeout", "max_output_tokens"),
    [
        ("low", 48_000, 270.0, 2048),
        ("medium", 128_000, 1350.0, 4096),
        ("high", 256_000, 1800.0, 8192),
        ("max", 512_000, 3600.0, 16_384),
    ],
)
def test_resolve_effort_profile_limits(
    effort: str,
    max_input_chars: int,
    request_timeout: float,
    max_output_tokens: int,
) -> None:
    runtime = resolve_llm_summary_runtime(llm_cfg=_llm_cfg(), effort=effort)
    assert runtime == LLMSummaryRuntime(
        effort=effort,  # type: ignore[arg-type]
        profile_name=effort,
        model="custom-model:7b",
        max_input_chars=max_input_chars,
        request_timeout=request_timeout,
        max_output_tokens=max_output_tokens,
    )
    assert isinstance(runtime.request_timeout, float)


@pytest.mark.unit
def test_high_and_max_exceed_medium_budgets() -> None:
    medium = resolve_llm_summary_runtime(llm_cfg=_llm_cfg(), effort="medium")
    high = resolve_llm_summary_runtime(llm_cfg=_llm_cfg(), effort="high")
    max_runtime = resolve_llm_summary_runtime(llm_cfg=_llm_cfg(), effort="max")
    assert high.max_input_chars > medium.max_input_chars
    assert high.max_output_tokens > medium.max_output_tokens
    assert max_runtime.max_input_chars > high.max_input_chars
    assert max_runtime.max_output_tokens > high.max_output_tokens


@pytest.mark.unit
def test_model_inherits_from_llm_cfg_when_profile_model_unset() -> None:
    runtime = resolve_llm_summary_runtime(
        llm_cfg=_llm_cfg(model="inherited:tag"),
        effort="medium",
    )
    assert runtime.model == "inherited:tag"


@pytest.mark.unit
def test_model_falls_back_to_default_ollama_model() -> None:
    runtime = resolve_llm_summary_runtime(
        llm_cfg=_llm_cfg(model=None),
        effort="medium",
    )
    assert runtime.model == DEFAULT_OLLAMA_MODEL


@pytest.mark.unit
def test_explicit_profile_model_override_wins() -> None:
    override_profiles = dict(BUILTIN_LLM_SUMMARY_EFFORT_PROFILES)
    override_profiles["medium"] = LLMSummaryEffortProfile(
        effort="medium",
        max_input_chars=128_000,
        request_timeout=1350.0,
        max_output_tokens=4096,
        model="override-model:13b",
    )
    runtime = resolve_llm_summary_runtime(
        llm_cfg=_llm_cfg(model="inherited:tag"),
        effort="medium",
        profiles=override_profiles,
    )
    assert runtime.model == "override-model:13b"


@pytest.mark.unit
def test_resolve_does_not_mutate_llm_cfg() -> None:
    llm_cfg = _llm_cfg()
    before = asdict(llm_cfg)
    resolve_llm_summary_runtime(llm_cfg=llm_cfg, effort="high")
    assert asdict(llm_cfg) == before


@pytest.mark.unit
def test_unknown_effort_raises() -> None:
    with pytest.raises(ValueError, match="Unknown llm_summary effort"):
        resolve_llm_summary_runtime(llm_cfg=_llm_cfg(), effort="turbo")


@pytest.mark.unit
def test_build_llm_summary_ollama_client_uses_runtime_limits() -> None:
    llm_cfg = _llm_cfg(request_timeout=999.0, max_output_tokens=9999)
    runtime = resolve_llm_summary_runtime(llm_cfg=llm_cfg, effort="low")
    client = build_llm_summary_ollama_client(llm_cfg=llm_cfg, runtime=runtime)
    assert client.model == "custom-model:7b"
    assert client._request_timeout == 270.0
    assert client._max_output_tokens == 2048


@pytest.mark.unit
def test_require_llm_summary_ollama_disabled_raises() -> None:
    with pytest.raises(LLMConfigurationError) as exc:
        require_llm_summary_ollama(_llm_cfg(enabled=False))
    assert exc.value.error_code == LLM_CONFIGURATION_ERROR


@pytest.mark.unit
def test_require_llm_summary_ollama_openai_raises() -> None:
    with pytest.raises(LLMConfigurationError) as exc:
        require_llm_summary_ollama(_llm_cfg(provider="openai"))
    assert exc.value.error_code == LLM_CONFIGURATION_ERROR


@pytest.mark.unit
def test_require_llm_summary_ollama_null_provider_raises() -> None:
    with pytest.raises(LLMConfigurationError) as exc:
        require_llm_summary_ollama(_llm_cfg(provider="null"))
    assert exc.value.error_code == LLM_CONFIGURATION_ERROR
