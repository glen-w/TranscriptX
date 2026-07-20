"""Tests for shared effort profiles and resolved analysis runtime."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from transcriptx.core.analysis.llm_support.runtime import (
    BUILTIN_LLM_EFFORT_PROFILES,
    LLMEffortProfile,
    LLMRuntime,
    build_input_coverage,
    build_ollama_analysis_client,
    get_llm_effort_profiles,
    require_ollama_analysis,
    resolve_llm_runtime,
)
from transcriptx.core.llm import DEFAULT_OLLAMA_MODEL
from transcriptx.core.llm.errors import LLM_CONFIGURATION_ERROR, LLMConfigurationError
from transcriptx.core.utils.config.system import LLMConfig


def _llm_cfg(**overrides: object) -> LLMConfig:
    cfg = LLMConfig()
    cfg.enabled = True
    cfg.provider = "ollama"
    cfg.model = "custom-model:7b"
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


@pytest.mark.unit
def test_effort_profile_limits_golden() -> None:
    assert {
        name: (p.max_input_chars, p.request_timeout, p.max_output_tokens)
        for name, p in BUILTIN_LLM_EFFORT_PROFILES.items()
    } == {
        "low": (48_000, 270.0, 2048),
        "medium": (128_000, 1350.0, 4096),
        "high": (256_000, 1800.0, 8192),
        "max": (512_000, 3600.0, 16_384),
    }


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
    runtime = resolve_llm_runtime(llm_cfg=_llm_cfg(), effort=effort)
    assert runtime == LLMRuntime(
        effort=effort,  # type: ignore[arg-type]
        profile_name=effort,
        model="custom-model:7b",
        max_input_chars=max_input_chars,
        request_timeout=request_timeout,
        max_output_tokens=max_output_tokens,
        model_source="global",
    )
    assert isinstance(runtime.request_timeout, float)


@pytest.mark.unit
def test_same_effort_resolves_identically_for_all_callers() -> None:
    """The three transcript-direct modules share one resolution path; the same
    effort name must resolve consistently regardless of caller."""
    runtime_a = resolve_llm_runtime(llm_cfg=_llm_cfg(), effort="high")
    runtime_b = resolve_llm_runtime(llm_cfg=_llm_cfg(), effort="high")
    assert runtime_a == runtime_b


@pytest.mark.unit
def test_effort_limits_replace_global_llm_limits() -> None:
    """Effort limits replace (never merge with) global llm.* limits."""
    cfg = _llm_cfg(max_input_chars=1234, request_timeout=999.0, max_output_tokens=777)
    runtime = resolve_llm_runtime(llm_cfg=cfg, effort="high")
    assert runtime.max_input_chars == 256_000
    assert runtime.request_timeout == 1800.0
    assert runtime.max_output_tokens == 8192


@pytest.mark.unit
def test_feature_default_efforts_unchanged() -> None:
    from transcriptx.core.config.models.llm_action_items import (
        LLMActionItemsSettingsModel,
    )
    from transcriptx.core.config.models.llm_speaker_summary import (
        LLMSpeakerSummarySettingsModel,
    )
    from transcriptx.core.config.models.llm_summary import LLMSummarySettingsModel

    assert LLMSummarySettingsModel().effort == "high"
    assert LLMSpeakerSummarySettingsModel().effort == "high"
    assert LLMActionItemsSettingsModel().effort == "high"


@pytest.mark.unit
def test_compatibility_aliases_removed() -> None:
    """The llm_summary_effort alias module must not exist after migration."""
    with pytest.raises(ModuleNotFoundError):
        import transcriptx.core.analysis.llm_summary_effort  # noqa: F401


@pytest.mark.unit
def test_high_and_max_exceed_medium_budgets() -> None:
    medium = resolve_llm_runtime(llm_cfg=_llm_cfg(), effort="medium")
    high = resolve_llm_runtime(llm_cfg=_llm_cfg(), effort="high")
    max_runtime = resolve_llm_runtime(llm_cfg=_llm_cfg(), effort="max")
    assert high.max_input_chars > medium.max_input_chars
    assert high.max_output_tokens > medium.max_output_tokens
    assert max_runtime.max_input_chars > high.max_input_chars
    assert max_runtime.max_output_tokens > high.max_output_tokens


@pytest.mark.unit
def test_model_inherits_from_llm_cfg_when_profile_model_unset() -> None:
    runtime = resolve_llm_runtime(
        llm_cfg=_llm_cfg(model="inherited:tag"),
        effort="medium",
    )
    assert runtime.model == "inherited:tag"


@pytest.mark.unit
def test_model_falls_back_to_default_ollama_model() -> None:
    runtime = resolve_llm_runtime(
        llm_cfg=_llm_cfg(model=None),
        effort="medium",
    )
    assert runtime.model == DEFAULT_OLLAMA_MODEL


@pytest.mark.unit
def test_explicit_profile_model_override_wins() -> None:
    override_profiles = dict(BUILTIN_LLM_EFFORT_PROFILES)
    override_profiles["medium"] = LLMEffortProfile(
        effort="medium",
        max_input_chars=128_000,
        request_timeout=1350.0,
        max_output_tokens=4096,
        model="override-model:13b",
    )
    runtime = resolve_llm_runtime(
        llm_cfg=_llm_cfg(model="inherited:tag"),
        effort="medium",
        profiles=override_profiles,
    )
    assert runtime.model == "override-model:13b"


@pytest.mark.unit
def test_consumer_id_ignores_effort_profile_model() -> None:
    """With consumer_id, effort-profile model is not part of precedence."""
    override_profiles = dict(BUILTIN_LLM_EFFORT_PROFILES)
    override_profiles["medium"] = LLMEffortProfile(
        effort="medium",
        max_input_chars=128_000,
        request_timeout=1350.0,
        max_output_tokens=4096,
        model="effort-only:13b",
    )
    runtime = resolve_llm_runtime(
        llm_cfg=_llm_cfg(model="global-tag:1"),
        effort="medium",
        profiles=override_profiles,
        consumer_id="llm_summary",
    )
    assert runtime.model == "global-tag:1"
    assert runtime.model_source == "global"


@pytest.mark.unit
def test_resolve_does_not_mutate_llm_cfg() -> None:
    llm_cfg = _llm_cfg()
    before = asdict(llm_cfg)
    resolve_llm_runtime(llm_cfg=llm_cfg, effort="high")
    assert asdict(llm_cfg) == before


@pytest.mark.unit
def test_unknown_effort_raises() -> None:
    with pytest.raises(ValueError, match="Unknown llm effort"):
        resolve_llm_runtime(llm_cfg=_llm_cfg(), effort="turbo")


@pytest.mark.unit
def test_build_ollama_analysis_client_uses_runtime_limits() -> None:
    llm_cfg = _llm_cfg(request_timeout=999.0, max_output_tokens=9999)
    runtime = resolve_llm_runtime(llm_cfg=llm_cfg, effort="low")
    client = build_ollama_analysis_client(llm_cfg=llm_cfg, runtime=runtime)
    assert client.model == "custom-model:7b"
    assert client._request_timeout == 270.0
    assert client._max_output_tokens == 2048


@pytest.mark.unit
def test_require_ollama_analysis_disabled_raises() -> None:
    with pytest.raises(LLMConfigurationError) as exc:
        require_ollama_analysis(_llm_cfg(enabled=False))
    assert exc.value.error_code == LLM_CONFIGURATION_ERROR


@pytest.mark.unit
def test_require_ollama_analysis_unsupported_provider_raises() -> None:
    with pytest.raises(LLMConfigurationError) as exc:
        require_ollama_analysis(_llm_cfg(provider="openai"))
    assert exc.value.error_code == LLM_CONFIGURATION_ERROR


@pytest.mark.unit
def test_require_ollama_analysis_null_provider_raises() -> None:
    with pytest.raises(LLMConfigurationError) as exc:
        require_ollama_analysis(_llm_cfg(provider="null"))
    assert exc.value.error_code == LLM_CONFIGURATION_ERROR


@pytest.mark.unit
def test_input_coverage_keys_golden() -> None:
    coverage = build_input_coverage(
        transcript_block="abc",
        trunc_meta={
            "truncated": True,
            "transcript_chars_total": 100,
            "transcript_chars_used": 60,
        },
    )
    assert coverage == {
        "input_truncated": True,
        "input_chars_total": 100,
        "input_chars_used": 60,
        "input_coverage_ratio": 0.6,
    }


@pytest.mark.unit
def test_require_ollama_analysis_azure_provider_raises() -> None:
    with pytest.raises(LLMConfigurationError, match="Unsupported LLM provider"):
        require_ollama_analysis(_llm_cfg(provider="azure"))


@pytest.mark.unit
def test_get_llm_effort_profiles_returns_defensive_copy() -> None:
    profiles = get_llm_effort_profiles()
    assert profiles == BUILTIN_LLM_EFFORT_PROFILES
    profiles.pop("low")
    assert "low" in BUILTIN_LLM_EFFORT_PROFILES


@pytest.mark.unit
def test_input_coverage_truncated_without_used_field_reports_zero() -> None:
    coverage = build_input_coverage(
        transcript_block="abcdef",
        trunc_meta={"truncated": True},
    )
    assert coverage == {
        "input_truncated": True,
        "input_chars_total": 6,
        "input_chars_used": 0,
        "input_coverage_ratio": 0.0,
    }


@pytest.mark.unit
def test_input_coverage_untruncated_without_used_field_reports_full() -> None:
    coverage = build_input_coverage(
        transcript_block="abcdef",
        trunc_meta={"truncated": False},
    )
    assert coverage == {
        "input_truncated": False,
        "input_chars_total": 6,
        "input_chars_used": 6,
        "input_coverage_ratio": 1.0,
    }


@pytest.mark.unit
def test_input_coverage_empty_transcript_ratio_is_one() -> None:
    coverage = build_input_coverage(transcript_block="", trunc_meta={})
    assert coverage["input_chars_total"] == 0
    assert coverage["input_coverage_ratio"] == 1.0


@pytest.mark.unit
def test_input_coverage_used_capped_at_ratio_one() -> None:
    coverage = build_input_coverage(
        transcript_block="ab",
        trunc_meta={
            "truncated": False,
            "transcript_chars_total": 10,
            "transcript_chars_used": 20,
        },
    )
    assert coverage["input_coverage_ratio"] == 1.0
