#!/usr/bin/env python3
"""Generate Pydantic config pilot models and golden fixtures (bridge is hand-maintained)."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import MISSING, fields, is_dataclass
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from transcriptx.core.utils.config import analysis as analysis_mod
from transcriptx.core.utils.config.system import (
    AudioPreprocessingConfig,
    LoggingConfig,
)
from transcriptx.core.utils.config.workflow import (
    GroupAnalysisConfig,
    InputConfig,
    OutputConfig,
    SpeakerGateConfig,
    WorkflowConfig,
)

MODELS_DIR = ROOT / "src" / "transcriptx" / "core" / "config" / "models"
FIXTURES_DIR = ROOT / "tests" / "core" / "config" / "fixtures"

PREPROCESSING_MODE = '"auto", "suggest", "off"'
GLOBAL_PREPROCESSING_MODE = '"selected", "auto", "suggest", "off"'


def _type_to_str(annotation: Any) -> str:
    if annotation is type(None):
        return "None"
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        if origin is type(None):
            return "None"
        if origin is list:
            inner = _type_to_str(args[0]) if args else "Any"
            return f"list[{inner}]"
        if origin is dict:
            key_t = _type_to_str(args[0]) if len(args) > 0 else "str"
            val_t = _type_to_str(args[1]) if len(args) > 1 else "Any"
            return f"dict[{key_t}, {val_t}]"
        if origin is tuple:
            if len(args) == 2 and args[1] is Ellipsis:
                return f"tuple[{_type_to_str(args[0])}, ...]"
            inner = ", ".join(_type_to_str(a) for a in args)
            return f"tuple[{inner}]"
        if origin is type(None) or str(origin) == "typing.Union":
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return f"{_type_to_str(non_none[0])} | None"
            return " | ".join(_type_to_str(a) for a in non_none)
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def _literal_from_str_options(options: tuple[str, ...]) -> str:
    quoted = ", ".join(f'"{o}"' for o in options)
    return f"Literal[{quoted}]"


def _default_repr(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, tuple):
        return repr(value)
    if isinstance(value, list):
        if len(value) > 8:
            return "field(default_factory=lambda: " + repr(value) + ")"
        return repr(value)
    if isinstance(value, dict):
        return "field(default_factory=lambda: " + repr(value) + ")"
    return repr(value)


def _segment_class_name(segment: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", segment)
    parts = [p for p in cleaned.split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def _scalar_dict_field_type(value: dict[str, Any]) -> str | None:
    if not value:
        return None
    if all(isinstance(v, bool) for v in value.values()):
        return "bool"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in value.values()):
        return "int"
    if all(isinstance(v, float) for v in value.values()):
        return "float"
    if all(isinstance(v, str) for v in value.values()):
        return "str"
    return None


def _collect_dict_nested_models(
    dc_cls: type,
    *,
    root_model_name: str,
    field_filter: set[str] | None,
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Build nested Pydantic models for dict[str, scalar] dataclass fields."""
    instance = dc_cls()
    extra_models: dict[str, list[str]] = {}
    field_types: dict[str, str] = {}
    for f in fields(dc_cls):
        if field_filter is not None and f.name not in field_filter:
            continue
        value = getattr(instance, f.name)
        if not isinstance(value, dict) or not value:
            continue
        scalar = _scalar_dict_field_type(value)
        if scalar is None:
            if all(isinstance(v, list) for v in value.values()):
                model_name = f"{root_model_name}{_segment_class_name(f.name)}Model"
                lines = [
                    f"    {key}: list[str] = Field(default_factory=lambda: {val!r})"
                    for key, val in value.items()
                ]
                extra_models[model_name] = lines
                field_types[f.name] = model_name
            continue
        model_name = f"{root_model_name}{_segment_class_name(f.name)}Model"
        lines = [
            f"    {key}: {scalar} = Field(default={val!r})"
            for key, val in value.items()
        ]
        extra_models[model_name] = lines
        field_types[f.name] = model_name
    return extra_models, field_types


def _generate_model_class(
    dc_cls: type,
    *,
    class_name: str,
    nested_map: dict[type, str],
    field_filter: set[str] | None = None,
    dict_field_types: dict[str, str] | None = None,
) -> str:
    import sys

    mod = sys.modules.get(dc_cls.__module__)
    globalns = mod.__dict__ if mod else {}
    try:
        hints = get_type_hints(dc_cls, globalns=globalns)
    except Exception:
        hints = {}
    lines: list[str] = []
    instance = dc_cls()
    for f in fields(dc_cls):
        if field_filter is not None and f.name not in field_filter:
            continue
        hint = hints.get(f.name, f.type)
        nested_name = nested_map.get(hint)
        if nested_name:
            type_str = nested_name
            default = f"Field(default_factory={nested_name})"
        elif dict_field_types and f.name in dict_field_types:
            type_str = dict_field_types[f.name]
            default = f"Field(default_factory={type_str})"
        else:
            type_str = _type_to_str(hint)
            value = getattr(instance, f.name)
            if f.default_factory is not MISSING:  # type: ignore[attr-defined]
                default = f"Field(default_factory=lambda: {repr(value)})"
            elif f.default is not MISSING:
                if isinstance(value, (list, dict)) and value:
                    default = f"Field(default_factory=lambda: {repr(value)})"
                else:
                    default = f"Field(default={_default_repr(value)})"
            else:
                default = "Field(...)"
        lines.append(f"    {f.name}: {type_str} = {default}")
    body = "\n".join(lines)
    return f"class {class_name}(BaseModel):\n{body}\n"


def _collect_nested_dataclasses(
    dc_cls: type, field_filter: set[str] | None
) -> list[type]:
    import sys

    mod = sys.modules.get(dc_cls.__module__)
    globalns = mod.__dict__ if mod else {}
    try:
        hints = get_type_hints(dc_cls, globalns=globalns)
    except Exception:
        hints = {}
    found: list[type] = []
    for f in fields(dc_cls):
        if field_filter is not None and f.name not in field_filter:
            continue
        hint = hints.get(f.name, f.type)
        origin = get_origin(hint)
        if origin is type(None) or str(origin) == "typing.Union":
            for arg in get_args(hint):
                if is_dataclass(arg):
                    found.append(arg)
        elif is_dataclass(hint):
            found.append(hint)
    return found


def _model_name_for_dataclass(dc_cls: type) -> str:
    base = dc_cls.__name__
    if base.endswith("Config"):
        return base.replace("Config", "SettingsModel")
    return f"{base}Model"


def generate_model_file(
    *,
    module_slug: str,
    title: str,
    root_dc: type,
    field_filter: set[str] | None = None,
    extra_imports: str = "",
    extra_code: str = "",
) -> str:
    nested_dcs: list[type] = []
    seen: set[type] = set()

    def walk(dc: type, filt: set[str] | None) -> None:
        for nested in _collect_nested_dataclasses(dc, filt):
            if nested not in seen:
                seen.add(nested)
                nested_dcs.append(nested)
                walk(nested, None)

    walk(root_dc, field_filter)
    nested_dcs.sort(key=lambda c: c.__name__)

    nested_map = {dc: _model_name_for_dataclass(dc) for dc in nested_dcs}
    root_model = _model_name_for_dataclass(root_dc)
    dict_models, dict_field_types = _collect_dict_nested_models(
        root_dc,
        root_model_name=root_model.replace("SettingsModel", ""),
        field_filter=field_filter,
    )

    parts = [
        f'"""Pydantic schema for {title}."""',
        "",
        "from typing import Any, Literal",
        "",
        "from pydantic import BaseModel, Field",
        extra_imports,
        "",
    ]
    for dc in nested_dcs:
        parts.append(
            _generate_model_class(
                dc,
                class_name=nested_map[dc],
                nested_map=nested_map,
                field_filter=None,
            )
        )
        parts.append("")
    for model_name, field_lines in dict_models.items():
        parts.append(f"class {model_name}(BaseModel):")
        parts.extend(field_lines)
        parts.append("")
    parts.append(
        _generate_model_class(
            root_dc,
            class_name=root_model,
            nested_map=nested_map,
            field_filter=field_filter,
            dict_field_types=dict_field_types,
        )
    )
    if extra_code:
        parts.append("")
        parts.append(extra_code)
    return "\n".join(parts).strip() + "\n"


PILOT_SPECS: list[dict[str, Any]] = [
    {
        "pilot_id": "dashboard_overview",
        "module": "dashboard_overview",
        "model_class": "DashboardOverviewSettingsModel",
        "dotpath_prefix": "dashboard",
        "category": "dashboard",
        "dataclass": None,
        "field_filter": {
            "schema_version",
            "overview_charts",
            "overview_missing_behavior",
            "overview_max_items",
        },
        "custom": True,
    },
    {
        "pilot_id": "output",
        "module": "output",
        "model_class": "OutputSettingsModel",
        "dotpath_prefix": "output",
        "category": "output",
        "dataclass": OutputConfig,
    },
    {
        "pilot_id": "input",
        "module": "input",
        "model_class": "InputSettingsModel",
        "dotpath_prefix": "input",
        "category": "input",
        "dataclass": InputConfig,
    },
    {
        "pilot_id": "logging",
        "module": "logging",
        "model_class": "LoggingSettingsModel",
        "dotpath_prefix": "logging",
        "category": "logging",
        "dataclass": LoggingConfig,
    },
    {
        "pilot_id": "group_analysis",
        "module": "group_analysis",
        "model_class": "GroupAnalysisSettingsModel",
        "dotpath_prefix": "group_analysis",
        "category": "group_analysis",
        "dataclass": GroupAnalysisConfig,
    },
    {
        "pilot_id": "audio_preprocessing",
        "module": "audio_preprocessing",
        "model_class": "AudioPreprocessingSettingsModel",
        "dotpath_prefix": "audio_preprocessing",
        "category": "audio_preprocessing",
        "dataclass": AudioPreprocessingConfig,
        "custom": True,
    },
    {
        "pilot_id": "topic_modeling",
        "module": "topic_modeling",
        "model_class": "TopicModelingSettingsModel",
        "dotpath_prefix": "analysis.topic_modeling",
        "category": "analysis",
        "dataclass": analysis_mod.TopicModelingConfig,
    },
    {
        "pilot_id": "qa_analysis",
        "module": "qa_analysis",
        "model_class": "QAAnalysisSettingsModel",
        "dotpath_prefix": "analysis.qa_analysis",
        "category": "analysis",
        "dataclass": analysis_mod.QAAnalysisConfig,
    },
    {
        "pilot_id": "temporal_dynamics",
        "module": "temporal_dynamics",
        "model_class": "TemporalDynamicsSettingsModel",
        "dotpath_prefix": "analysis.temporal_dynamics",
        "category": "analysis",
        "dataclass": analysis_mod.TemporalDynamicsConfig,
    },
    {
        "pilot_id": "vectorization",
        "module": "vectorization",
        "model_class": "VectorizationSettingsModel",
        "dotpath_prefix": "analysis.vectorization",
        "category": "analysis",
        "dataclass": analysis_mod.VectorizationConfig,
    },
    {
        "pilot_id": "tag_extraction",
        "module": "tag_extraction",
        "model_class": "TagExtractionSettingsModel",
        "dotpath_prefix": "analysis.tag_extraction",
        "category": "analysis",
        "dataclass": analysis_mod.TagExtractionConfig,
    },
    {
        "pilot_id": "workflow",
        "module": "workflow",
        "model_class": "WorkflowSettingsModel",
        "dotpath_prefix": "workflow",
        "category": "workflow",
        "dataclass": WorkflowConfig,
    },
    {
        "pilot_id": "speaker_exemplars",
        "module": "speaker_exemplars",
        "model_class": "SpeakerExemplarsSettingsModel",
        "dotpath_prefix": "analysis.speaker_exemplars",
        "category": "analysis",
        "dataclass": analysis_mod.SpeakerExemplarsConfig,
    },
    {
        "pilot_id": "highlights",
        "module": "highlights",
        "model_class": "HighlightsSettingsModel",
        "dotpath_prefix": "analysis.highlights",
        "category": "analysis",
        "dataclass": analysis_mod.HighlightsConfig,
    },
    {
        "pilot_id": "summary",
        "module": "summary",
        "model_class": "SummarySettingsModel",
        "dotpath_prefix": "analysis.summary",
        "category": "analysis",
        "dataclass": analysis_mod.SummaryConfig,
    },
    {
        "pilot_id": "corrections",
        "module": "corrections",
        "model_class": "CorrectionsSettingsModel",
        "dotpath_prefix": "analysis.corrections",
        "category": "analysis",
        "dataclass": analysis_mod.CorrectionsConfig,
    },
    {
        "pilot_id": "voice",
        "module": "voice",
        "model_class": "VoiceSettingsModel",
        "dotpath_prefix": "analysis.voice",
        "category": "analysis",
        "dataclass": analysis_mod.VoiceConfig,
    },
    {
        "pilot_id": "affect_tension",
        "module": "affect_tension",
        "model_class": "AffectTensionSettingsModel",
        "dotpath_prefix": "analysis.affect_tension",
        "category": "analysis",
        "dataclass": analysis_mod.AffectTensionConfig,
    },
    {
        "pilot_id": "echoes",
        "module": "echoes",
        "model_class": "EchoesSettingsModel",
        "dotpath_prefix": "analysis.echoes",
        "category": "analysis",
        "dataclass": analysis_mod.EchoesConfig,
    },
    {
        "pilot_id": "momentum",
        "module": "momentum",
        "model_class": "MomentumSettingsModel",
        "dotpath_prefix": "analysis.momentum",
        "category": "analysis",
        "dataclass": analysis_mod.MomentumConfig,
    },
    {
        "pilot_id": "moments",
        "module": "moments",
        "model_class": "MomentsSettingsModel",
        "dotpath_prefix": "analysis.moments",
        "category": "analysis",
        "dataclass": analysis_mod.MomentsConfig,
    },
    {
        "pilot_id": "pauses",
        "module": "pauses",
        "model_class": "PausesSettingsModel",
        "dotpath_prefix": "analysis.pauses",
        "category": "analysis",
        "dataclass": analysis_mod.PausesConfig,
    },
    {
        "pilot_id": "bertopic",
        "module": "bertopic",
        "model_class": "BERTopicSettingsModel",
        "dotpath_prefix": "analysis.bertopic",
        "category": "analysis",
        "dataclass": analysis_mod.BERTopicConfig,
    },
]

DICT_PROFILE_PILOTS: list[dict[str, Any]] = [
    {
        "pilot_id": "quality_filtering_profiles",
        "module": "quality_filtering_profiles",
        "model_class": "QualityFilteringProfilesSettingsModel",
        "dotpath_prefix": "analysis.quality_filtering_profiles",
        "category": "analysis",
    },
    {
        "pilot_id": "semantic_similarity_v2_profiles",
        "module": "semantic_similarity_v2_profiles",
        "model_class": "SemanticSimilarityV2ProfilesSettingsModel",
        "dotpath_prefix": "analysis.semantic_similarity_v2_profiles",
        "category": "analysis",
    },
    {
        "pilot_id": "quick_analysis_settings",
        "module": "quick_analysis_settings",
        "model_class": "QuickAnalysisSettingsModel",
        "dotpath_prefix": "analysis.quick_analysis_settings",
        "category": "analysis",
    },
    {
        "pilot_id": "full_analysis_settings",
        "module": "full_analysis_settings",
        "model_class": "FullAnalysisSettingsModel",
        "dotpath_prefix": "analysis.full_analysis_settings",
        "category": "analysis",
    },
]


ANALYSIS_PARTIAL: list[dict[str, Any]] = [
    {
        "pilot_id": "analysis_sentiment",
        "module": "analysis_sentiment",
        "model_class": "AnalysisSentimentSettingsModel",
        "fields": [
            "sentiment_window_size",
            "sentiment_min_confidence",
            "emotion_min_confidence",
            "emotion_model_name",
            "emotion_output_mode",
            "emotion_score_threshold",
            "sentiment_backend",
            "sentiment_model_name",
        ],
    },
    {
        "pilot_id": "analysis_ner",
        "module": "analysis_ner",
        "model_class": "AnalysisNerSettingsModel",
        "fields": [
            "ner_labels",
            "ner_min_confidence",
            "ner_include_geocoding",
            "ner_use_light_model",
            "ner_max_segments",
            "ner_batch_size",
        ],
    },
    {
        "pilot_id": "analysis_wordcloud",
        "module": "analysis_wordcloud",
        "model_class": "AnalysisWordcloudSettingsModel",
        "fields": [
            "wordcloud_max_words",
            "wordcloud_min_font_size",
            "wordcloud_stopwords",
            "exclude_unidentified_from_speaker_charts",
            "readability_metrics",
        ],
    },
    {
        "pilot_id": "analysis_interaction",
        "module": "analysis_interaction",
        "model_class": "AnalysisInteractionSettingsModel",
        "fields": [
            "interaction_overlap_threshold",
            "interaction_min_gap",
            "interaction_min_segment_length",
            "interaction_response_threshold",
            "interaction_include_responses",
            "interaction_include_overlaps",
            "interaction_min_interactions",
            "interaction_time_window",
            "loop_max_intermediate_turns",
            "loop_exclude_monologues",
            "loop_min_gap",
            "loop_max_gap",
        ],
    },
    {
        "pilot_id": "analysis_entity",
        "module": "analysis_entity",
        "model_class": "AnalysisEntitySettingsModel",
        "fields": [
            "entity_min_mentions",
            "entity_types",
            "entity_sentiment_threshold",
        ],
    },
    {
        "pilot_id": "analysis_legacy_semantic",
        "module": "analysis_legacy_semantic",
        "model_class": "AnalysisLegacySemanticSettingsModel",
        "fields": [
            "semantic_similarity_threshold",
            "cross_speaker_similarity_threshold",
            "repetition_time_window",
            "cross_speaker_time_window",
            "semantic_model_name",
            "clustering_eps",
            "clustering_min_samples",
            "max_segments_for_semantic",
            "max_segments_per_speaker",
            "max_segments_for_cross_speaker",
            "use_quality_filtering",
            "min_segment_quality_score",
            "quality_filtering_profile",
            "semantic_similarity_method",
            "quality_weights_override",
            "quality_thresholds_override",
            "quality_indicators_override",
            "max_semantic_comparisons",
            "semantic_timeout_seconds",
            "semantic_batch_size",
            "semantic_progress_log_interval_seconds",
            "module_progress_log_interval_seconds",
            "output_formats",
            "analysis_mode",
            "include_legacy_modules",
        ],
    },
]


def write_dashboard_overview() -> None:
    content = '''"""Pydantic schema for dashboard overview settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


def _chart_choices() -> list[str]:
    try:
        from transcriptx.core.utils.chart_registry import get_chart_registry

        return sorted(get_chart_registry().keys())
    except Exception:
        return []


def _default_overview_charts() -> list[str]:
    try:
        from transcriptx.core.utils.chart_registry import get_default_overview_charts

        return get_default_overview_charts()
    except Exception:
        return []


class DashboardOverviewSettingsModel(BaseModel):
    """Canonical field definitions for dashboard overview chart selection."""

    schema_version: int = Field(default=2, ge=1, description="Dashboard config schema version.")
    overview_charts: list[str] = Field(
        default_factory=_default_overview_charts,
        description="Ordered list of chart registry IDs for the overview.",
        json_schema_extra={"choices": _chart_choices()},
    )
    overview_missing_behavior: Literal["skip", "show_placeholder"] = Field(
        default="skip",
        description="Behavior when overview charts are missing.",
    )
    overview_max_items: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of overview charts to display.",
    )
'''
    (MODELS_DIR / "dashboard_overview.py").write_text(content)


def write_audio_preprocessing() -> None:
    inst = AudioPreprocessingConfig()
    content = f'''"""Pydantic schema for audio preprocessing settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PreprocessingMode = Literal[{PREPROCESSING_MODE}]
GlobalPreprocessingMode = Literal[{GLOBAL_PREPROCESSING_MODE}]
DenoiseStrength = Literal["low", "medium", "high"]


class AudioPreprocessingSettingsModel(BaseModel):
    """Canonical field definitions for audio preprocessing configuration."""

    preprocessing_mode: GlobalPreprocessingMode = Field(default={inst.preprocessing_mode!r})
    convert_to_mono: PreprocessingMode = Field(default={inst.convert_to_mono!r})
    downsample: PreprocessingMode = Field(default={inst.downsample!r})
    target_sample_rate: int = Field(default={inst.target_sample_rate})
    skip_if_already_compliant: bool = Field(default={inst.skip_if_already_compliant})
    normalize_mode: PreprocessingMode = Field(default={inst.normalize_mode!r})
    target_lufs: float = Field(default={inst.target_lufs}, ge=-20.0, le=-16.0)
    limiter_enabled: bool = Field(default={inst.limiter_enabled})
    limiter_peak_db: float = Field(default={inst.limiter_peak_db})
    denoise_mode: PreprocessingMode = Field(default={inst.denoise_mode!r})
    denoise_strength: DenoiseStrength = Field(default={inst.denoise_strength!r})
    highpass_mode: PreprocessingMode = Field(default={inst.highpass_mode!r})
    highpass_cutoff: int = Field(default={inst.highpass_cutoff}, ge=70, le=100)
    lowpass_mode: PreprocessingMode = Field(default={inst.lowpass_mode!r})
    lowpass_cutoff: int = Field(default={inst.lowpass_cutoff})
    bandpass_mode: PreprocessingMode = Field(default={inst.bandpass_mode!r})
    bandpass_low: int = Field(default={inst.bandpass_low})
    bandpass_high: int = Field(default={inst.bandpass_high})
'''
    (MODELS_DIR / "audio_preprocessing.py").write_text(content)


def write_output_model() -> None:
    content = '''"""Pydantic schema for output settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from transcriptx.core.utils.paths import (
    DIARISED_TRANSCRIPTS_DIR,
    OUTPUTS_DIR,
    READABLE_TRANSCRIPTS_DIR,
    RECORDINGS_DIR,
)

DynamicMode = Literal["auto", "on", "off"]


class OutputSettingsModel(BaseModel):
    """Canonical field definitions for output paths and artifact generation."""

    base_output_dir: str = Field(default_factory=lambda: str(OUTPUTS_DIR))
    create_subdirectories: bool = Field(default=True)
    overwrite_existing: bool = Field(default=False)
    dynamic_charts: DynamicMode = Field(
        default="auto",
        description="Dynamic chart generation mode.",
    )
    dynamic_views: DynamicMode = Field(
        default="auto",
        description="Dynamic HTML view generation mode.",
    )
    default_audio_folder: str = Field(default_factory=lambda: str(RECORDINGS_DIR))
    default_transcript_folder: str = Field(
        default_factory=lambda: str(DIARISED_TRANSCRIPTS_DIR)
    )
    default_readable_transcript_folder: str = Field(
        default_factory=lambda: str(READABLE_TRANSCRIPTS_DIR)
    )
    audio_deduplication_threshold: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
    )
'''
    (MODELS_DIR / "output.py").write_text(content)


def write_group_analysis_model() -> None:
    content = '''"""Pydantic schema for group_analysis."""

from pydantic import BaseModel, Field

from transcriptx.core.utils.paths import GROUP_OUTPUTS_DIR


class GroupAnalysisSettingsModel(BaseModel):
    enabled: bool = Field(default=True)
    output_dir: str = Field(default_factory=lambda: str(GROUP_OUTPUTS_DIR))
    persist_groups: bool = Field(default=False)
    enable_stats_aggregation: bool = Field(default=True)
    scaffold_by_session: bool = Field(default=True)
    scaffold_by_speaker: bool = Field(default=True)
    scaffold_comparisons: bool = Field(default=True)
    wordcloud_pooled_emit_full_transcript_global: bool = Field(default=False)
    wordcloud_pooled_global_tfidf: bool = Field(default=False)
'''
    (MODELS_DIR / "group_analysis.py").write_text(content)


def write_input_model() -> None:
    content = '''"""Pydantic schema for input settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from transcriptx.core.utils.paths import RECORDINGS_DIR

FileSelectionMode = Literal["prompt", "explore", "direct"]


class InputSettingsModel(BaseModel):
    """Canonical field definitions for input discovery and file selection."""

    wav_folders: list[str] = Field(default_factory=lambda: ["/Volumes/DVT1600/RECORD/A"])
    recordings_folders: list[str] = Field(
        default_factory=lambda: [str(RECORDINGS_DIR)]
    )
    prefill_rename_with_date_prefix: bool = Field(default=True)
    file_selection_mode: FileSelectionMode = Field(default="prompt")
    playback_skip_seconds_short: float = Field(default=10.0)
    playback_skip_seconds_long: float = Field(default=60.0)
'''
    (MODELS_DIR / "input.py").write_text(content)


def write_partial_analysis(spec: dict[str, Any]) -> None:
    inst = analysis_mod.AnalysisConfig()
    field_lines: list[str] = []
    for name in spec["fields"]:
        f = analysis_mod.AnalysisConfig.__dataclass_fields__[name]
        value = getattr(inst, name)
        hint = f.type
        type_str = _type_to_str(hint)
        if isinstance(value, (list, dict)) and value:
            default = f"Field(default_factory=lambda: {repr(value)})"
        else:
            default = f"Field(default={_default_repr(value)})"
        field_lines.append(f"    {name}: {type_str} = {default}")
    body = "\n".join(field_lines)
    content = f'''"""Pydantic schema for analysis.{spec["pilot_id"]} settings."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class {spec["model_class"]}(BaseModel):
    """Partial analysis.* scalar fields for {spec["pilot_id"]}."""

{body}
'''
    (MODELS_DIR / f"{spec['module']}.py").write_text(content)


def write_workflow_model() -> None:
    wf = WorkflowConfig()
    sg = SpeakerGateConfig()
    content = f'''"""Pydantic schema for workflow settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ThresholdType = Literal["absolute", "percentage"]
SpeakerGateMode = Literal["ignore", "warn", "enforce"]


class SpeakerGateSettingsModel(BaseModel):
    """Speaker identification gate settings."""

    threshold_value: float = Field(default={sg.threshold_value}, ge=0.0)
    threshold_type: ThresholdType = Field(default={sg.threshold_type!r})
    mode: SpeakerGateMode = Field(default={sg.mode!r})
    exemplar_count: int = Field(default={sg.exemplar_count}, ge=0)


class WorkflowSettingsModel(BaseModel):
    """Canonical field definitions for workflow and batch processing."""

    timeout_quick_seconds: int = Field(default={wf.timeout_quick_seconds}, ge=1)
    timeout_full_seconds: int = Field(default={wf.timeout_full_seconds}, ge=1)
    update_interval: float = Field(default={wf.update_interval}, ge=0.1)
    max_size_mb: int = Field(default={wf.max_size_mb}, ge=1)
    subprocess_timeout: int = Field(default={wf.subprocess_timeout}, ge=1)
    mp3_bitrate: str = Field(default={wf.mp3_bitrate!r})
    conversion_time_factor: float = Field(default={wf.conversion_time_factor}, ge=0.0)
    speaker_gate: SpeakerGateSettingsModel = Field(default_factory=SpeakerGateSettingsModel)
    cli_pruning_enabled: bool = Field(default={wf.cli_pruning_enabled})
    default_config_save_path: str = Field(default={wf.default_config_save_path!r})
'''
    (MODELS_DIR / "workflow.py").write_text(content)


def generate_standard_models() -> None:
    write_dashboard_overview()
    write_output_model()
    write_input_model()
    write_group_analysis_model()
    write_audio_preprocessing()
    write_workflow_model()
    for spec in PILOT_SPECS:
        if spec.get("custom"):
            continue
        if spec["pilot_id"] in {
            "dashboard_overview",
            "output",
            "input",
            "group_analysis",
            "audio_preprocessing",
            "workflow",
        }:
            continue
        filt = spec.get("field_filter")
        content = generate_model_file(
            module_slug=spec["module"],
            title=spec["dotpath_prefix"],
            root_dc=spec["dataclass"],
            field_filter=set(filt) if filt else None,
        )
        (MODELS_DIR / f"{spec['module']}.py").write_text(content)
    for spec in ANALYSIS_PARTIAL:
        write_partial_analysis(spec)


def write_goldens() -> None:
    from transcriptx.core.config.pydantic_bridge import (
        PYDANTIC_REGISTRY_PILOTS,
        capture_pilot_schema_golden,
        serialize_non_pydantic_registry_baseline,
    )
    from transcriptx.core.config.registry import build_registry, get_default_config_dict

    for spec in PYDANTIC_REGISTRY_PILOTS:
        golden = capture_pilot_schema_golden(spec)
        path = FIXTURES_DIR / f"{spec.pilot_id}_registry_golden.json"
        path.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n")
        if spec.dataclass_type is not None:
            from dataclasses import asdict

            defaults = asdict(spec.dataclass_type())
            defaults_path = FIXTURES_DIR / f"{spec.pilot_id}_defaults_golden.json"
            defaults_path.write_text(
                json.dumps(defaults, indent=2, sort_keys=True) + "\n"
            )
        elif spec.pilot_id == "dashboard_overview":
            from transcriptx.core.config.models.dashboard_overview import (
                DashboardOverviewSettingsModel,
            )

            dash = get_default_config_dict()["dashboard"]
            keys = list(DashboardOverviewSettingsModel.model_fields)
            subset = {k: dash[k] for k in keys}
            (FIXTURES_DIR / "dashboard_overview_defaults_golden.json").write_text(
                json.dumps(subset, indent=2, sort_keys=True) + "\n"
            )
        elif spec.dotpath_prefix == "analysis" and spec.pilot_id.startswith(
            "analysis_"
        ):
            inst = analysis_mod.AnalysisConfig()
            subset = {f: getattr(inst, f) for f in spec.model.model_fields}
            (FIXTURES_DIR / f"{spec.pilot_id}_defaults_golden.json").write_text(
                json.dumps(subset, indent=2, sort_keys=True) + "\n"
            )
        elif spec.pilot_id == "dashboard_display":
            from transcriptx.core.config.models.dashboard_display import (
                DashboardDisplaySettingsModel,
            )

            dash = get_default_config_dict()["dashboard"]
            keys = list(DashboardDisplaySettingsModel.model_fields)
            subset = {k: dash[k] for k in keys}
            (FIXTURES_DIR / "dashboard_display_defaults_golden.json").write_text(
                json.dumps(subset, indent=2, sort_keys=True) + "\n"
            )

    reg = build_registry()
    baseline = serialize_non_pydantic_registry_baseline(reg)
    (FIXTURES_DIR / "non_pydantic_registry_baseline.json").write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n"
    )


def write_bridge_scaffold() -> str:
    """Emit mechanical PydanticPilotSpec rows for pasting into pydantic_bridge.py."""
    hand_curated = {
        "semantic_similarity_v2",
        "metadata",
        "dashboard_display",
        "llm",
        "acts",
    }
    model_imports: set[str] = set()
    dataclass_imports: set[str] = set()
    spec_lines: list[str] = []

    def _add_spec(
        *,
        pilot_id: str,
        model_class: str,
        module: str,
        dotpath_prefix: str,
        category: str,
        dataclass: Any,
    ) -> None:
        if pilot_id in hand_curated:
            return
        model_imports.add(f"from .models.{module} import {model_class}")
        dc_repr = "None"
        if dataclass is not None:
            dc_repr = dataclass.__name__
            dataclass_imports.add(dataclass.__name__)
        spec_lines.append(
            f"    PydanticPilotSpec(\n"
            f'        pilot_id="{pilot_id}",\n'
            f"        model={model_class},\n"
            f'        dotpath_prefix="{dotpath_prefix}",\n'
            f'        category="{category}",\n'
            f"        dataclass_type={dc_repr},\n"
            f"    ),"
        )

    for spec in PILOT_SPECS:
        _add_spec(
            pilot_id=spec["pilot_id"],
            model_class=spec["model_class"],
            module=spec["module"],
            dotpath_prefix=spec["dotpath_prefix"],
            category=spec["category"],
            dataclass=spec.get("dataclass"),
        )
    for spec in DICT_PROFILE_PILOTS:
        _add_spec(
            pilot_id=spec["pilot_id"],
            model_class=spec["model_class"],
            module=spec["module"],
            dotpath_prefix=spec["dotpath_prefix"],
            category=spec["category"],
            dataclass=None,
        )
    for spec in ANALYSIS_PARTIAL:
        _add_spec(
            pilot_id=spec["pilot_id"],
            model_class=spec["model_class"],
            module=spec["module"],
            dotpath_prefix="analysis",
            category="analysis",
            dataclass=None,
        )

    lines = [
        "# Paste into pydantic_bridge.py -> PYDANTIC_REGISTRY_PILOTS",
        "# Review ordering and merge with hand-curated pilots before committing.",
        "# Behavioral bridge logic lives in pydantic_bridge_helpers.py (never generate).",
        "",
        "# Hand-curated pilots (keep in bridge manually, not in this scaffold):",
        "#   semantic_similarity_v2, metadata, dashboard_display, llm, acts",
        "",
        "# Suggested model imports (merge into pydantic_bridge.py):",
    ]
    lines.extend(f"# {imp}" for imp in sorted(model_imports))
    if dataclass_imports:
        lines.append(
            "# Suggested dataclass imports (merge from existing bridge imports):"
        )
        lines.extend(f"# {name}" for name in sorted(dataclass_imports))
    lines.extend(
        [
            "",
            "PYDANTIC_REGISTRY_PILOTS: tuple[PydanticPilotSpec, ...] = (",
            *spec_lines,
            ")",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Default (no flags): regenerate models and golden fixtures. "
            "Never modifies pydantic_bridge.py (hand-maintained)."
        )
    )
    parser.add_argument(
        "--models-only",
        action="store_true",
        help="Regenerate model files only (requires explicit flag).",
    )
    parser.add_argument(
        "--fixtures-only",
        action="store_true",
        help="Regenerate golden fixture JSON files only.",
    )
    parser.add_argument(
        "--write-bridge",
        action="store_true",
        help=(
            "Print scaffold for PYDANTIC_REGISTRY_PILOTS pilot rows only "
            "(does not modify pydantic_bridge.py)."
        ),
    )
    parser.add_argument(
        "--write-bridge-to",
        metavar="PATH",
        help="Write --write-bridge scaffold output to PATH instead of stdout.",
    )
    args = parser.parse_args()

    if args.write_bridge or args.write_bridge_to:
        scaffold = write_bridge_scaffold()
        if args.write_bridge_to:
            Path(args.write_bridge_to).write_text(scaffold, encoding="utf-8")
            print(f"Wrote bridge scaffold to {args.write_bridge_to}")
        else:
            print(scaffold, end="")
        return

    any_flag = args.models_only or args.fixtures_only
    run_models = args.models_only or not any_flag
    run_fixtures = args.fixtures_only or not any_flag

    if run_models:
        generate_standard_models()
        sys.path.insert(0, str(ROOT / "scripts"))
        from generate_dict_profile_models import (
            write_analysis_presets,
            write_quality_filtering_profiles,
            write_semantic_v2_profiles,
        )

        write_quality_filtering_profiles()
        write_semantic_v2_profiles()
        write_analysis_presets()

    if run_fixtures:
        write_goldens()

    if not run_models and not run_fixtures:
        parser.print_help()
        return

    parts = []
    if run_models:
        parts.append("models")
    if run_fixtures:
        parts.append("fixtures")
    print(f"Generated: {', '.join(parts)}.")


if __name__ == "__main__":
    main()
