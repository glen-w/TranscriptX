#!/usr/bin/env python3
"""Generate Pydantic models for dictionary-backed config profile stores."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transcriptx.core.utils.config.analysis import AnalysisConfig

MODELS_DIR = ROOT / "src" / "transcriptx" / "core" / "config" / "models"


def _class_name(segment: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", segment)
    parts = [p for p in cleaned.split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def _field_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        if value and all(isinstance(x, str) for x in value):
            return "list[str]"
        return "list[Any]"
    if isinstance(value, tuple):
        if value and all(isinstance(x, (int, float)) for x in value):
            inner = "int" if all(isinstance(x, int) for x in value) else "float"
            return f"tuple[{inner}, {inner}]"
        return "tuple[Any, ...]"
    if isinstance(value, dict):
        raise TypeError("dict values must be converted to nested models")
    return "Any"


def _build_models_from_dict(
    data: dict[str, Any],
    *,
    class_name: str,
    models: dict[str, list[str]],
) -> str:
    field_lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            nested_name = f"{class_name}{_class_name(key)}Model"
            _build_models_from_dict(value, class_name=nested_name, models=models)
            field_lines.append(
                f"    {key}: {nested_name} = Field(default_factory={nested_name})"
            )
        else:
            type_str = _field_type(value)
            if isinstance(value, (list, tuple)) and value:
                field_lines.append(
                    f"    {key}: {type_str} = Field(default_factory=lambda: {value!r})"
                )
            else:
                field_lines.append(f"    {key}: {type_str} = Field(default={value!r})")
    models[class_name] = field_lines
    return class_name


def render_module(
    *,
    module_doc: str,
    root_class: str,
    data: dict[str, Any],
) -> str:
    models: dict[str, list[str]] = {}
    _build_models_from_dict(data, class_name=root_class, models=models)
    parts = [
        f'"""{module_doc}"""',
        "",
        "from typing import Any",
        "",
        "from pydantic import BaseModel, Field",
        "",
    ]
    for class_name, field_lines in models.items():
        parts.append(f"class {class_name}(BaseModel):")
        parts.extend(field_lines or ["    pass"])
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def write_quality_filtering_profiles() -> None:
    profiles = AnalysisConfig().quality_filtering_profiles
    content = render_module(
        module_doc="Pydantic schema for analysis.quality_filtering_profiles.",
        root_class="QualityFilteringProfilesSettingsModel",
        data=profiles,
    )
    (MODELS_DIR / "quality_filtering_profiles.py").write_text(content)


def write_semantic_v2_profiles() -> None:
    profiles = AnalysisConfig().semantic_similarity_v2_profiles
    content = render_module(
        module_doc="Pydantic schema for analysis.semantic_similarity_v2_profiles.",
        root_class="SemanticSimilarityV2ProfilesSettingsModel",
        data=profiles,
    )
    (MODELS_DIR / "semantic_similarity_v2_profiles.py").write_text(content)


def write_analysis_presets() -> None:
    inst = AnalysisConfig()
    quick = render_module(
        module_doc="Pydantic schema for analysis.quick_analysis_settings preset.",
        root_class="QuickAnalysisSettingsModel",
        data=inst.quick_analysis_settings,
    )
    (MODELS_DIR / "quick_analysis_settings.py").write_text(quick)
    full = render_module(
        module_doc="Pydantic schema for analysis.full_analysis_settings preset.",
        root_class="FullAnalysisSettingsModel",
        data=inst.full_analysis_settings,
    )
    (MODELS_DIR / "full_analysis_settings.py").write_text(full)


def main() -> None:
    write_quality_filtering_profiles()
    write_semantic_v2_profiles()
    write_analysis_presets()
    print("Generated dict profile store models.")


if __name__ == "__main__":
    main()
