"""Registry of Pydantic config pilots and shared bridge helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Type

from pydantic import BaseModel

from transcriptx.core.utils.config.analysis import (
    ActsConfig,
    AffectTensionConfig,
    BERTopicConfig,
    CorrectionsConfig,
    EchoesConfig,
    HighlightsConfig,
    MomentsConfig,
    MomentumConfig,
    PausesConfig,
    QAAnalysisConfig,
    SemanticSimilarityV2Config,
    SpeakerExemplarsConfig,
    SummaryConfig,
    LLMSummaryConfig,
    LLMSpeakerSummaryConfig,
    TagExtractionConfig,
    TemporalDynamicsConfig,
    TopicModelingConfig,
    VectorizationConfig,
    VoiceConfig,
)
from transcriptx.core.utils.config.system import (
    AudioPreprocessingConfig,
    LLMConfig,
    LoggingConfig,
)
from transcriptx.core.utils.config.workflow import (
    GroupAnalysisConfig,
    InputConfig,
    MetadataConfig,
    OutputConfig,
    WorkflowConfig,
)

from .models.acts import ActsSettingsModel
from .models.affect_tension import AffectTensionSettingsModel
from .models.analysis_entity import AnalysisEntitySettingsModel
from .models.analysis_interaction import AnalysisInteractionSettingsModel
from .models.analysis_legacy_semantic import AnalysisLegacySemanticSettingsModel
from .models.analysis_ner import AnalysisNerSettingsModel
from .models.analysis_sentiment import AnalysisSentimentSettingsModel
from .models.analysis_wordcloud import AnalysisWordcloudSettingsModel
from .models.audio_preprocessing import AudioPreprocessingSettingsModel
from .models.bertopic import BERTopicSettingsModel
from .models.corrections import CorrectionsSettingsModel
from .models.dashboard_display import DashboardDisplaySettingsModel
from .models.dashboard_overview import DashboardOverviewSettingsModel
from .models.echoes import EchoesSettingsModel
from .models.full_analysis_settings import FullAnalysisSettingsModel
from .models.group_analysis import GroupAnalysisSettingsModel
from .models.highlights import HighlightsSettingsModel
from .models.input import InputSettingsModel
from .models.llm import LLMSettingsModel
from .models.llm_summary import LLMSummarySettingsModel
from .models.llm_speaker_summary import LLMSpeakerSummarySettingsModel
from .models.logging import LoggingSettingsModel
from .models.metadata import MetadataSettingsModel
from .models.moments import MomentsSettingsModel
from .models.momentum import MomentumSettingsModel
from .models.output import OutputSettingsModel
from .models.pauses import PausesSettingsModel
from .models.qa_analysis import QAAnalysisSettingsModel
from .models.quality_filtering_profiles import QualityFilteringProfilesSettingsModel
from .models.quick_analysis_settings import QuickAnalysisSettingsModel
from .models.semantic_similarity_v2 import SemanticSimilarityV2SettingsModel
from .models.semantic_similarity_v2_profiles import (
    SemanticSimilarityV2ProfilesSettingsModel,
)
from .models.speaker_exemplars import SpeakerExemplarsSettingsModel
from .models.summary import SummarySettingsModel
from .models.tag_extraction import TagExtractionSettingsModel
from .models.temporal_dynamics import TemporalDynamicsSettingsModel
from .models.topic_modeling import TopicModelingSettingsModel
from .models.vectorization import VectorizationSettingsModel
from .models.voice import VoiceSettingsModel
from .models.workflow import WorkflowSettingsModel

from .pydantic_bridge_helpers import (
    dotpath_belongs_to_model,
    extract_subtree_overrides as extract_subtree_overrides_for_model,
)
from .pydantic_registry import (
    collect_model_leaf_dotpaths,
    pydantic_model_to_field_metadata,
    serialize_field_metadata,
)
from .registry import FieldMetadata

SEMANTIC_SIMILARITY_V2_PREFIX = "analysis.semantic_similarity_v2"


@dataclass(frozen=True)
class PydanticPilotSpec:
    """One incrementally migrated config subtree backed by Pydantic."""

    pilot_id: str
    model: Type[BaseModel]
    dotpath_prefix: str
    category: str = ""
    dataclass_type: Type[Any] | None = None

    @property
    def dotpath_prefix_with_dot(self) -> str:
        return f"{self.dotpath_prefix}."


def _category_for(spec: PydanticPilotSpec) -> str:
    if spec.category:
        return spec.category
    if "." in spec.dotpath_prefix:
        return spec.dotpath_prefix.split(".", 1)[0]
    return spec.dotpath_prefix


PYDANTIC_REGISTRY_PILOTS: tuple[PydanticPilotSpec, ...] = (
    PydanticPilotSpec(
        pilot_id="semantic_similarity_v2",
        model=SemanticSimilarityV2SettingsModel,
        dotpath_prefix=SEMANTIC_SIMILARITY_V2_PREFIX,
        category="analysis",
        dataclass_type=SemanticSimilarityV2Config,
    ),
    PydanticPilotSpec(
        pilot_id="metadata",
        model=MetadataSettingsModel,
        dotpath_prefix="metadata",
        category="metadata",
        dataclass_type=MetadataConfig,
    ),
    PydanticPilotSpec(
        pilot_id="dashboard_display",
        model=DashboardDisplaySettingsModel,
        dotpath_prefix="dashboard",
        category="dashboard",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="llm",
        model=LLMSettingsModel,
        dotpath_prefix="llm",
        category="llm",
        dataclass_type=LLMConfig,
    ),
    PydanticPilotSpec(
        pilot_id="acts",
        model=ActsSettingsModel,
        dotpath_prefix="analysis.acts",
        category="analysis",
        dataclass_type=ActsConfig,
    ),
    PydanticPilotSpec(
        pilot_id="dashboard_overview",
        model=DashboardOverviewSettingsModel,
        dotpath_prefix="dashboard",
        category="dashboard",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="output",
        model=OutputSettingsModel,
        dotpath_prefix="output",
        category="output",
        dataclass_type=OutputConfig,
    ),
    PydanticPilotSpec(
        pilot_id="input",
        model=InputSettingsModel,
        dotpath_prefix="input",
        category="input",
        dataclass_type=InputConfig,
    ),
    PydanticPilotSpec(
        pilot_id="logging",
        model=LoggingSettingsModel,
        dotpath_prefix="logging",
        category="logging",
        dataclass_type=LoggingConfig,
    ),
    PydanticPilotSpec(
        pilot_id="group_analysis",
        model=GroupAnalysisSettingsModel,
        dotpath_prefix="group_analysis",
        category="group_analysis",
        dataclass_type=GroupAnalysisConfig,
    ),
    PydanticPilotSpec(
        pilot_id="audio_preprocessing",
        model=AudioPreprocessingSettingsModel,
        dotpath_prefix="audio_preprocessing",
        category="audio_preprocessing",
        dataclass_type=AudioPreprocessingConfig,
    ),
    PydanticPilotSpec(
        pilot_id="topic_modeling",
        model=TopicModelingSettingsModel,
        dotpath_prefix="analysis.topic_modeling",
        category="analysis",
        dataclass_type=TopicModelingConfig,
    ),
    PydanticPilotSpec(
        pilot_id="qa_analysis",
        model=QAAnalysisSettingsModel,
        dotpath_prefix="analysis.qa_analysis",
        category="analysis",
        dataclass_type=QAAnalysisConfig,
    ),
    PydanticPilotSpec(
        pilot_id="temporal_dynamics",
        model=TemporalDynamicsSettingsModel,
        dotpath_prefix="analysis.temporal_dynamics",
        category="analysis",
        dataclass_type=TemporalDynamicsConfig,
    ),
    PydanticPilotSpec(
        pilot_id="vectorization",
        model=VectorizationSettingsModel,
        dotpath_prefix="analysis.vectorization",
        category="analysis",
        dataclass_type=VectorizationConfig,
    ),
    PydanticPilotSpec(
        pilot_id="tag_extraction",
        model=TagExtractionSettingsModel,
        dotpath_prefix="analysis.tag_extraction",
        category="analysis",
        dataclass_type=TagExtractionConfig,
    ),
    PydanticPilotSpec(
        pilot_id="llm_summary_settings",
        model=LLMSummarySettingsModel,
        dotpath_prefix="analysis.llm_summary",
        category="analysis",
        dataclass_type=LLMSummaryConfig,
    ),
    PydanticPilotSpec(
        pilot_id="llm_speaker_summary_settings",
        model=LLMSpeakerSummarySettingsModel,
        dotpath_prefix="analysis.llm_speaker_summary",
        category="analysis",
        dataclass_type=LLMSpeakerSummaryConfig,
    ),
    PydanticPilotSpec(
        pilot_id="workflow",
        model=WorkflowSettingsModel,
        dotpath_prefix="workflow",
        category="workflow",
        dataclass_type=WorkflowConfig,
    ),
    PydanticPilotSpec(
        pilot_id="speaker_exemplars",
        model=SpeakerExemplarsSettingsModel,
        dotpath_prefix="analysis.speaker_exemplars",
        category="analysis",
        dataclass_type=SpeakerExemplarsConfig,
    ),
    PydanticPilotSpec(
        pilot_id="highlights",
        model=HighlightsSettingsModel,
        dotpath_prefix="analysis.highlights",
        category="analysis",
        dataclass_type=HighlightsConfig,
    ),
    PydanticPilotSpec(
        pilot_id="summary",
        model=SummarySettingsModel,
        dotpath_prefix="analysis.summary",
        category="analysis",
        dataclass_type=SummaryConfig,
    ),
    PydanticPilotSpec(
        pilot_id="corrections",
        model=CorrectionsSettingsModel,
        dotpath_prefix="analysis.corrections",
        category="analysis",
        dataclass_type=CorrectionsConfig,
    ),
    PydanticPilotSpec(
        pilot_id="voice",
        model=VoiceSettingsModel,
        dotpath_prefix="analysis.voice",
        category="analysis",
        dataclass_type=VoiceConfig,
    ),
    PydanticPilotSpec(
        pilot_id="affect_tension",
        model=AffectTensionSettingsModel,
        dotpath_prefix="analysis.affect_tension",
        category="analysis",
        dataclass_type=AffectTensionConfig,
    ),
    PydanticPilotSpec(
        pilot_id="echoes",
        model=EchoesSettingsModel,
        dotpath_prefix="analysis.echoes",
        category="analysis",
        dataclass_type=EchoesConfig,
    ),
    PydanticPilotSpec(
        pilot_id="momentum",
        model=MomentumSettingsModel,
        dotpath_prefix="analysis.momentum",
        category="analysis",
        dataclass_type=MomentumConfig,
    ),
    PydanticPilotSpec(
        pilot_id="moments",
        model=MomentsSettingsModel,
        dotpath_prefix="analysis.moments",
        category="analysis",
        dataclass_type=MomentsConfig,
    ),
    PydanticPilotSpec(
        pilot_id="pauses",
        model=PausesSettingsModel,
        dotpath_prefix="analysis.pauses",
        category="analysis",
        dataclass_type=PausesConfig,
    ),
    PydanticPilotSpec(
        pilot_id="bertopic",
        model=BERTopicSettingsModel,
        dotpath_prefix="analysis.bertopic",
        category="analysis",
        dataclass_type=BERTopicConfig,
    ),
    PydanticPilotSpec(
        pilot_id="analysis_sentiment",
        model=AnalysisSentimentSettingsModel,
        dotpath_prefix="analysis",
        category="analysis",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="analysis_ner",
        model=AnalysisNerSettingsModel,
        dotpath_prefix="analysis",
        category="analysis",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="analysis_wordcloud",
        model=AnalysisWordcloudSettingsModel,
        dotpath_prefix="analysis",
        category="analysis",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="analysis_interaction",
        model=AnalysisInteractionSettingsModel,
        dotpath_prefix="analysis",
        category="analysis",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="analysis_entity",
        model=AnalysisEntitySettingsModel,
        dotpath_prefix="analysis",
        category="analysis",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="analysis_legacy_semantic",
        model=AnalysisLegacySemanticSettingsModel,
        dotpath_prefix="analysis",
        category="analysis",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="quality_filtering_profiles",
        model=QualityFilteringProfilesSettingsModel,
        dotpath_prefix="analysis.quality_filtering_profiles",
        category="analysis",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="semantic_similarity_v2_profiles",
        model=SemanticSimilarityV2ProfilesSettingsModel,
        dotpath_prefix="analysis.semantic_similarity_v2_profiles",
        category="analysis",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="quick_analysis_settings",
        model=QuickAnalysisSettingsModel,
        dotpath_prefix="analysis.quick_analysis_settings",
        category="analysis",
        dataclass_type=None,
    ),
    PydanticPilotSpec(
        pilot_id="full_analysis_settings",
        model=FullAnalysisSettingsModel,
        dotpath_prefix="analysis.full_analysis_settings",
        category="analysis",
        dataclass_type=None,
    ),
)

PYDANTIC_VALIDATED_PREFIXES: tuple[str, ...] = tuple(
    spec.dotpath_prefix_with_dot for spec in PYDANTIC_REGISTRY_PILOTS
)


def pilot_field_names(spec: PydanticPilotSpec) -> frozenset[str]:
    return frozenset(spec.model.model_fields.keys())


def pilot_field_dotpath(spec: PydanticPilotSpec, field_name: str) -> str:
    return f"{spec.dotpath_prefix}.{field_name}"


def all_pydantic_field_dotpaths() -> frozenset[str]:
    keys: set[str] = set()
    for spec in PYDANTIC_REGISTRY_PILOTS:
        keys.update(
            collect_model_leaf_dotpaths(
                spec.model,
                dotpath_prefix=spec.dotpath_prefix,
            )
        )
    return frozenset(keys)


def find_pilot_for_dotpath_key(key: str) -> PydanticPilotSpec | None:
    for spec in PYDANTIC_REGISTRY_PILOTS:
        if dotpath_belongs_to_model(
            key,
            dotpath_prefix=spec.dotpath_prefix,
            model=spec.model,
        ):
            return spec
    return None


def is_pydantic_validated_field_key(key: str) -> bool:
    return find_pilot_for_dotpath_key(key) is not None


def apply_pydantic_registry_overrides(registry: Dict[str, FieldMetadata]) -> None:
    """Overwrite registry entries for all registered Pydantic pilots."""
    for spec in PYDANTIC_REGISTRY_PILOTS:
        registry.update(
            pydantic_model_to_field_metadata(
                spec.model,
                dotpath_prefix=spec.dotpath_prefix,
                category=_category_for(spec),
            )
        )


def capture_pilot_schema_golden(spec: PydanticPilotSpec) -> Dict[str, Dict[str, Any]]:
    """Build serializable registry metadata for one pilot subtree."""
    metadata = pydantic_model_to_field_metadata(
        spec.model,
        dotpath_prefix=spec.dotpath_prefix,
        category=_category_for(spec),
    )
    return {
        key: serialize_field_metadata(meta) for key, meta in sorted(metadata.items())
    }


def extract_subtree_overrides(
    flattened: Dict[str, Any],
    spec: PydanticPilotSpec,
) -> Dict[str, Any]:
    return extract_subtree_overrides_for_model(
        flattened,
        dotpath_prefix=spec.dotpath_prefix,
        model=spec.model,
    )


def serialize_non_pydantic_registry_baseline(
    registry: Dict[str, FieldMetadata],
) -> Dict[str, Dict[str, Any]]:
    """Serialize registry keys that are not owned by any Pydantic pilot field."""
    pilot_keys = all_pydantic_field_dotpaths()
    return {
        key: serialize_field_metadata(meta)
        for key, meta in sorted(registry.items())
        if key not in pilot_keys
    }
