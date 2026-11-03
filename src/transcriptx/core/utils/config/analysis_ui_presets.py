"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class PresetPolicyConfig:
    """One UI analysis preset policy. Defaults owned by PresetPolicyModel."""

    allow_llm: bool = field(init=False, repr=True)
    llm_module_ids: list = field(init=False, repr=True)
    allow_heavy: bool = field(init=False, repr=True)
    heavy_module_ids: list = field(init=False, repr=True)
    include_excluded_from_default: bool = field(init=False, repr=True)
    module_ids: object = field(init=False, repr=True)


@dataclass
class AnalysisUiPresetsConfig:
    """Defaults owned by AnalysisUiPresetsModel."""

    quick: PresetPolicyConfig = field(init=False, repr=True)
    balanced: PresetPolicyConfig = field(init=False, repr=True)
    thorough: PresetPolicyConfig = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.ui_presets import AnalysisUiPresetsModel

        _hydrate_dataclass_from_pydantic(self, AnalysisUiPresetsModel())


def default_ui_presets_dict() -> dict[str, Any]:
    """Builtin Quick/Balanced/Thorough policies as a plain nested dict."""
    from dataclasses import asdict

    return asdict(AnalysisUiPresetsConfig())


def validate_ui_presets_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a ui_presets payload; return model_dump()."""
    from transcriptx.core.config.models.ui_presets import AnalysisUiPresetsModel

    return AnalysisUiPresetsModel.model_validate(payload).model_dump()
