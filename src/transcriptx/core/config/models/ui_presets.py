"""Pydantic schema for analysis.ui_presets (Quick / Balanced / Thorough policies)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class QuickPresetPolicyModel(BaseModel):
    """Quick preset: no LLM, no heavy modules."""

    model_config = ConfigDict(extra="forbid")

    allow_llm: bool = Field(
        default=False,
        description="Whether modules with requires_llm may be included.",
    )
    llm_module_ids: list[str] = Field(
        default_factory=list,
        description=(
            "When allow_llm is true: empty means all LLM modules; "
            "non-empty is an allowlist."
        ),
    )
    allow_heavy: bool = Field(
        default=False,
        description=(
            "Whether heavy modules (cost_tier or category == heavy) may be included."
        ),
    )
    heavy_module_ids: list[str] = Field(
        default_factory=list,
        description=(
            "When allow_heavy is true: empty means all heavy modules; "
            "non-empty is an allowlist."
        ),
    )
    include_excluded_from_default: bool = Field(
        default=False,
        description="Include modules marked exclude_from_default in the registry.",
    )
    module_ids: Optional[list[str]] = Field(
        default=None,
        description=(
            "Optional full module override. null = apply policy; "
            "list = use this set (intersected with suitable modules)."
        ),
    )


class BalancedPresetPolicyModel(BaseModel):
    """Balanced: limited heavy allowlist + llm_summary only."""

    model_config = ConfigDict(extra="forbid")

    allow_llm: bool = Field(
        default=True,
        description="Whether modules with requires_llm may be included.",
    )
    llm_module_ids: list[str] = Field(
        default_factory=lambda: ["llm_summary"],
        description=(
            "When allow_llm is true: empty means all LLM modules; "
            "non-empty is an allowlist."
        ),
    )
    allow_heavy: bool = Field(
        default=True,
        description=(
            "Whether heavy modules (cost_tier or category == heavy) may be included."
        ),
    )
    heavy_module_ids: list[str] = Field(
        default_factory=lambda: [
            "semantic_similarity_v2",
            "fine_grained_emotion",
        ],
        description=(
            "When allow_heavy is true: empty means all heavy modules; "
            "non-empty is an allowlist."
        ),
    )
    include_excluded_from_default: bool = Field(
        default=False,
        description="Include modules marked exclude_from_default in the registry.",
    )
    module_ids: Optional[list[str]] = Field(
        default=None,
        description=(
            "Optional full module override. null = apply policy; "
            "list = use this set (intersected with suitable modules)."
        ),
    )


class ThoroughPresetPolicyModel(BaseModel):
    """Thorough: all suitable modules (LLM + heavy + exclude-from-default)."""

    model_config = ConfigDict(extra="forbid")

    allow_llm: bool = Field(
        default=True,
        description="Whether modules with requires_llm may be included.",
    )
    llm_module_ids: list[str] = Field(
        default_factory=list,
        description=(
            "When allow_llm is true: empty means all LLM modules; "
            "non-empty is an allowlist."
        ),
    )
    allow_heavy: bool = Field(
        default=True,
        description=(
            "Whether heavy modules (cost_tier or category == heavy) may be included."
        ),
    )
    heavy_module_ids: list[str] = Field(
        default_factory=list,
        description=(
            "When allow_heavy is true: empty means all heavy modules; "
            "non-empty is an allowlist."
        ),
    )
    include_excluded_from_default: bool = Field(
        default=True,
        description="Include modules marked exclude_from_default in the registry.",
    )
    module_ids: Optional[list[str]] = Field(
        default=None,
        description=(
            "Optional full module override. null = apply policy; "
            "list = use this set (intersected with suitable modules)."
        ),
    )


class AnalysisUiPresetsModel(BaseModel):
    """Project-level UI analysis preset policies and optional overrides."""

    model_config = ConfigDict(extra="forbid")

    quick: QuickPresetPolicyModel = Field(default_factory=QuickPresetPolicyModel)
    balanced: BalancedPresetPolicyModel = Field(
        default_factory=BalancedPresetPolicyModel
    )
    thorough: ThoroughPresetPolicyModel = Field(
        default_factory=ThoroughPresetPolicyModel
    )
