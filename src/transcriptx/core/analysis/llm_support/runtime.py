"""Effort profiles and resolved runtime for transcript-direct LLM analysis.

This is analysis policy (effort tiers, Ollama eligibility, input coverage),
kept out of the ``core.llm`` provider layer. Client construction delegates to
the generic provider factory in :mod:`transcriptx.core.llm.ollama_client`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from transcriptx.core.config.models.llm_summary import LLMSummaryEffort
from transcriptx.core.llm import DEFAULT_OLLAMA_MODEL
from transcriptx.core.llm.errors import LLMConfigurationError
from transcriptx.core.llm.ollama_client import OllamaClient, build_ollama_client

__all__ = [
    "LLMEffortProfile",
    "LLMRuntime",
    "BUILTIN_LLM_EFFORT_PROFILES",
    "get_llm_effort_profiles",
    "require_ollama_analysis",
    "resolve_llm_runtime",
    "build_ollama_analysis_client",
    "build_input_coverage",
]

_NULL_LLM_CLIENT_MESSAGE = (
    "LLM client not configured. Please configure an LLM provider in the config file."
)


@dataclass(frozen=True)
class LLMEffortProfile:
    """Immutable builtin limits for one effort tier."""

    effort: LLMSummaryEffort
    max_input_chars: int
    request_timeout: float
    max_output_tokens: int
    model: str | None = None


@dataclass(frozen=True)
class LLMRuntime:
    """Resolved execution parameters for one transcript-direct module run."""

    effort: LLMSummaryEffort
    profile_name: str
    model: str
    max_input_chars: int
    request_timeout: float
    max_output_tokens: int


BUILTIN_LLM_EFFORT_PROFILES: dict[LLMSummaryEffort, LLMEffortProfile] = {
    "low": LLMEffortProfile(
        effort="low",
        max_input_chars=48_000,
        request_timeout=270.0,
        max_output_tokens=2048,
    ),
    "medium": LLMEffortProfile(
        effort="medium",
        max_input_chars=128_000,
        request_timeout=1350.0,
        max_output_tokens=4096,
    ),
    "high": LLMEffortProfile(
        effort="high",
        max_input_chars=256_000,
        request_timeout=1800.0,
        max_output_tokens=8192,
    ),
    "max": LLMEffortProfile(
        effort="max",
        max_input_chars=512_000,
        request_timeout=3600.0,
        max_output_tokens=16_384,
    ),
}


def get_llm_effort_profiles() -> dict[LLMSummaryEffort, LLMEffortProfile]:
    """Return the builtin effort profile map (tests/future overrides use resolve kwarg)."""
    return dict(BUILTIN_LLM_EFFORT_PROFILES)


def require_ollama_analysis(llm_cfg: Any) -> None:
    """Mirror ``get_llm_client()`` eligibility for Ollama effort-path modules."""
    provider = (llm_cfg.provider or "null").strip().lower()
    if not llm_cfg.enabled or provider in ("null", ""):
        raise LLMConfigurationError(_NULL_LLM_CLIENT_MESSAGE)
    if provider != "ollama":
        raise LLMConfigurationError(f"Unsupported LLM provider: {llm_cfg.provider!r}")


def resolve_llm_runtime(
    *,
    llm_cfg: Any,
    effort: str,
    profiles: Mapping[LLMSummaryEffort, LLMEffortProfile] | None = None,
) -> LLMRuntime:
    """Return resolved effort limits without mutating ``llm_cfg``.

    Effort-profile limits replace (never merge with) the global ``llm.*``
    values for the calling module.
    """
    profile_map = profiles or BUILTIN_LLM_EFFORT_PROFILES
    normalized = str(effort).strip().lower()
    profile = profile_map.get(normalized)  # type: ignore[arg-type]
    if profile is None:
        raise ValueError(f"Unknown llm effort: {effort!r}")

    model = profile.model or llm_cfg.model or DEFAULT_OLLAMA_MODEL
    return LLMRuntime(
        effort=profile.effort,
        profile_name=profile.effort,
        model=str(model),
        max_input_chars=int(profile.max_input_chars),
        request_timeout=float(profile.request_timeout),
        max_output_tokens=int(profile.max_output_tokens),
    )


def build_ollama_analysis_client(
    *,
    llm_cfg: Any,
    runtime: LLMRuntime,
) -> OllamaClient:
    """Instantiate Ollama for a transcript-direct module using resolved limits."""
    return build_ollama_client(
        base_url=llm_cfg.base_url,
        model=runtime.model,
        seed=int(llm_cfg.seed),
        request_timeout=float(runtime.request_timeout),
        availability_timeout=float(llm_cfg.availability_timeout),
        max_output_tokens=runtime.max_output_tokens,
    )


def build_input_coverage(
    *,
    transcript_block: str,
    trunc_meta: dict[str, Any],
) -> dict[str, Any]:
    """Build wrapper-excluded transcript coverage fields for provenance."""
    total_raw = trunc_meta.get("transcript_chars_total")
    used_raw = trunc_meta.get("transcript_chars_used")
    input_chars_total = (
        int(total_raw) if isinstance(total_raw, int) else len(transcript_block or "")
    )
    if isinstance(used_raw, int):
        input_chars_used = used_raw
    elif bool(trunc_meta.get("truncated", False)):
        input_chars_used = 0
    else:
        input_chars_used = input_chars_total

    if input_chars_total <= 0:
        input_coverage_ratio = 1.0
    else:
        input_coverage_ratio = min(1.0, input_chars_used / input_chars_total)

    return {
        "input_truncated": bool(trunc_meta.get("truncated", False)),
        "input_chars_total": input_chars_total,
        "input_chars_used": input_chars_used,
        "input_coverage_ratio": input_coverage_ratio,
    }
