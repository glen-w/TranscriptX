"""Analysis configuration classes (facade).

Nested dataclasses live in ``analysis_*.py`` modules 1:1 with Pydantic pilots.
``AnalysisConfig`` remains here: it hydrates several flat slices and mapping stores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .analysis_hydrate import (
    _dataclass_from_nested_dump,
    _hydrate_analysis_slice,
    _hydrate_dataclass_from_pydantic,
    _hydrate_mapping_store,
)
from .analysis_acts import ActsConfig
from .analysis_affect_tension import AffectTensionConfig
from .analysis_bertopic import BERTopicConfig
from .analysis_chart_descriptions import ChartDescriptionsConfig
from .analysis_corrections import CorrectionsConfig
from .analysis_corrections_llm import CorrectionsLlmConfig
from .analysis_echoes import EchoesConfig
from .analysis_emotion_family import (
    ContextualEmotionConfig,
    EmotionLexicalConfig,
    FineGrainedEmotionConfig,
)
from .analysis_epistemic_markers import EpistemicMarkersConfig
from .analysis_group_llm_synthesis import GroupLLMSynthesisConfig
from .analysis_highlights import (
    HighlightsColdOpen,
    HighlightsConfig,
    HighlightsConflict,
    HighlightsCounts,
    HighlightsMergeAdjacent,
    HighlightsOutput,
    HighlightsSections,
    HighlightsThresholds,
    HighlightsWeights,
)
from .analysis_insight_eligibility import InsightEligibilityConfig
from .analysis_insights import InsightsConfig, InsightsCounts
from .analysis_keyphrases import KeyphrasesConfig
from .analysis_llm_action_items import LLMActionItemsConfig
from .analysis_llm_custom_qa import LLMCustomQAConfig
from .analysis_llm_speaker_summary import LLMSpeakerSummaryConfig
from .analysis_llm_summary import LLMSummaryConfig
from .analysis_moments import MomentsConfig
from .analysis_momentum import MomentumConfig
from .analysis_names import NamesConfig
from .analysis_pauses import PausesConfig
from .analysis_politeness import PolitenessConfig
from .analysis_qa_analysis import QAAnalysisConfig
from .analysis_semantic_similarity import SemanticSimilarityConfig
from .analysis_speaker_exemplars import SpeakerExemplarsConfig
from .analysis_summary import (
    SummaryCommitments,
    SummaryConfig,
    SummaryCounts,
    SummarySections,
)
from .analysis_tag_extraction import TagExtractionConfig
from .analysis_temporal_dynamics import TemporalDynamicsConfig
from .analysis_topic_modeling import TopicModelingConfig
from .analysis_topic_shift import TopicShiftConfig
from .analysis_transcript_quality import TranscriptQualityConfig
from .analysis_ui_presets import (
    AnalysisUiPresetsConfig,
    PresetPolicyConfig,
    default_ui_presets_dict,
    validate_ui_presets_dict,
)
from .analysis_vectorization import VectorizationConfig
from .analysis_voice import VoiceConfig

__all__ = [
    "ActsConfig",
    "AffectTensionConfig",
    "AnalysisConfig",
    "AnalysisUiPresetsConfig",
    "BERTopicConfig",
    "ChartDescriptionsConfig",
    "ContextualEmotionConfig",
    "CorrectionsConfig",
    "CorrectionsLlmConfig",
    "EchoesConfig",
    "EmotionLexicalConfig",
    "EpistemicMarkersConfig",
    "FineGrainedEmotionConfig",
    "GroupLLMSynthesisConfig",
    "HighlightsColdOpen",
    "HighlightsConfig",
    "HighlightsConflict",
    "HighlightsCounts",
    "HighlightsMergeAdjacent",
    "HighlightsOutput",
    "HighlightsSections",
    "HighlightsThresholds",
    "HighlightsWeights",
    "InsightEligibilityConfig",
    "InsightsConfig",
    "InsightsCounts",
    "KeyphrasesConfig",
    "LLMActionItemsConfig",
    "LLMCustomQAConfig",
    "LLMSpeakerSummaryConfig",
    "LLMSummaryConfig",
    "MomentsConfig",
    "MomentumConfig",
    "NamesConfig",
    "PausesConfig",
    "PolitenessConfig",
    "PresetPolicyConfig",
    "QAAnalysisConfig",
    "SemanticSimilarityConfig",
    "SpeakerExemplarsConfig",
    "SummaryCommitments",
    "SummaryConfig",
    "SummaryCounts",
    "SummarySections",
    "TagExtractionConfig",
    "TemporalDynamicsConfig",
    "TopicModelingConfig",
    "TopicShiftConfig",
    "TranscriptQualityConfig",
    "VectorizationConfig",
    "VoiceConfig",
    "_dataclass_from_nested_dump",
    "_hydrate_analysis_slice",
    "_hydrate_dataclass_from_pydantic",
    "_hydrate_mapping_store",
    "default_ui_presets_dict",
    "validate_ui_presets_dict",
]


@dataclass
class AnalysisConfig:
    """
    Configuration for analysis modules.

    This dataclass contains all the parameters that control how the various
    analysis modules behave. It includes settings for sentiment analysis,
    emotion detection, NER, word clouds, speaker interactions, and more.

    The configuration is designed to be flexible and allows fine-tuning
    of analysis behavior for different types of conversations and use cases.
    """

    # Sentiment analysis settings
    # Control the window size and confidence thresholds for sentiment analysis
    sentiment_window_size: int = field(init=False, repr=True)
    sentiment_min_confidence: float = field(init=False, repr=True)

    # Emotion analysis settings
    # Control the emotion detection model and confidence thresholds
    emotion_min_confidence: float = field(init=False, repr=True)
    emotion_model_name: str = field(init=False, repr=True)
    emotion_output_mode: str = field(init=False, repr=True)
    emotion_score_threshold: float = field(init=False, repr=True)

    # Sentiment analysis backend
    sentiment_backend: str = field(init=False, repr=True)
    sentiment_model_name: str = field(init=False, repr=True)

    # NER analysis settings
    # Control which entities to extract and how to process them
    ner_labels: list[str] = field(init=False, repr=True)
    ner_min_confidence: float = field(init=False, repr=True)
    ner_include_geocoding: bool = field(init=False, repr=True)
    ner_use_light_model: bool = field(init=False, repr=True)
    ner_max_segments: int = field(init=False, repr=True)
    ner_batch_size: int = field(init=False, repr=True)

    # Word clouds settings
    # Control the generation and appearance of word clouds
    wordcloud_max_words: int = field(init=False, repr=True)
    wordcloud_min_font_size: int = field(init=False, repr=True)
    wordcloud_stopwords: list[str] = field(init=False, repr=True)
    # When True, per-speaker charts/data only for named speakers
    exclude_unidentified_from_speaker_charts: bool = field(init=False, repr=True)
    # When True, run modules on diarized labels (SPEAKER_00, …) without naming
    allow_unnamed_speakers: bool = field(init=False, repr=True)
    # T1: monologue opt-in when exactly one turn-taking speaker exists
    treat_as_single_speaker: bool = field(init=False, repr=True)

    # Corrections settings
    corrections: CorrectionsConfig = field(default_factory=CorrectionsConfig)

    # Speaker exemplars settings
    speaker_exemplars: SpeakerExemplarsConfig = field(
        default_factory=SpeakerExemplarsConfig
    )

    # Highlights and summary settings
    highlights: HighlightsConfig = field(default_factory=HighlightsConfig)
    summary: SummaryConfig = field(default_factory=SummaryConfig)
    insights: "InsightsConfig" = field(default_factory=lambda: InsightsConfig())
    insight_eligibility: "InsightEligibilityConfig" = field(
        default_factory=lambda: InsightEligibilityConfig()
    )

    # Understandability settings
    # Control which readability metrics to calculate
    readability_metrics: list[str] = field(init=False, repr=True)

    # Speaker interactions analysis settings (unified networks + interruptions)
    # Control how speaker interactions are detected and analyzed
    interaction_overlap_threshold: float = field(init=False, repr=True)
    interaction_min_gap: float = field(init=False, repr=True)
    interaction_min_segment_length: float = field(init=False, repr=True)
    interaction_response_threshold: float = field(init=False, repr=True)
    interaction_include_responses: bool = field(init=False, repr=True)
    interaction_include_overlaps: bool = field(init=False, repr=True)
    interaction_min_interactions: int = field(init=False, repr=True)
    interaction_time_window: float = field(init=False, repr=True)

    # Entity sentiment analysis settings
    # Control how entity-focused sentiment analysis works
    entity_min_mentions: int = field(init=False, repr=True)
    entity_types: list[str] = field(init=False, repr=True)
    entity_sentiment_threshold: float = field(init=False, repr=True)

    # Conversation loop detection settings
    # Control how conversation patterns and loops are identified
    loop_max_intermediate_turns: int = field(init=False, repr=True)
    loop_exclude_monologues: bool = field(init=False, repr=True)
    loop_min_gap: float = field(init=False, repr=True)
    loop_max_gap: float = field(init=False, repr=True)

    # Semantic similarity and repetition detection settings
    # Control how semantic similarity analysis and repetition detection work
    semantic_similarity_threshold: float = field(init=False, repr=True)
    cross_speaker_similarity_threshold: float = field(init=False, repr=True)
    repetition_time_window: float = field(init=False, repr=True)
    cross_speaker_time_window: float = field(init=False, repr=True)
    semantic_model_name: str = field(init=False, repr=True)
    clustering_eps: float = field(init=False, repr=True)
    clustering_min_samples: int = field(init=False, repr=True)

    # Performance limits for semantic similarity (to prevent hanging)
    # These settings help prevent the system from processing too much data
    max_segments_for_semantic: int = field(init=False, repr=True)
    max_segments_per_speaker: int = field(init=False, repr=True)
    max_segments_for_cross_speaker: int = field(init=False, repr=True)
    use_quality_filtering: bool = field(init=False, repr=True)
    min_segment_quality_score: float = field(init=False, repr=True)

    # Quality filtering profile system
    # Different profiles optimize for different types of conversations
    quality_filtering_profile: str = field(init=False, repr=True)
    semantic_similarity_method: str = field(init=False, repr=True)
    quality_filtering_profiles: dict[str, dict[str, Any]] = field(init=False, repr=True)

    # Individual override options (these override profile settings)
    quality_weights_override: dict[str, float] | None = field(init=False, repr=True)
    quality_thresholds_override: dict[str, Any] | None = field(init=False, repr=True)
    quality_indicators_override: dict[str, list[str]] | None = field(
        init=False, repr=True
    )

    max_semantic_comparisons: int = field(init=False, repr=True)
    semantic_timeout_seconds: int = field(init=False, repr=True)
    semantic_batch_size: int = field(init=False, repr=True)
    semantic_progress_log_interval_seconds: float = field(init=False, repr=True)
    module_progress_log_interval_seconds: float = field(init=False, repr=True)

    # General
    output_formats: list[str] = field(init=False, repr=True)
    use_dag_pipeline: bool = True  # Use DAG pipeline for better dependency management

    # When True, legacy analysis modules marked `legacy` in the registry are included
    # in default module lists. Default False: only explicit module IDs run legacy paths.
    include_legacy_modules: bool = field(init=False, repr=True)

    # Quick vs Full Analysis Mode
    analysis_mode: str = field(init=False, repr=True)
    quick_analysis_settings: dict[str, Any] = field(init=False, repr=True)
    full_analysis_settings: dict[str, Any] = field(init=False, repr=True)

    # Semantic similarity v2 (default semantic path; legacy IDs remain selectable)
    semantic_similarity: SemanticSimilarityConfig = field(
        default_factory=SemanticSimilarityConfig
    )
    active_semantic_similarity_profile: str = "balanced"
    semantic_similarity_profiles: dict[str, dict[str, Any]] = field(
        init=False, repr=True
    )

    # Module-specific configurations
    topic_modeling: TopicModelingConfig = field(
        default_factory=lambda: TopicModelingConfig()
    )
    bertopic: BERTopicConfig = field(default_factory=lambda: BERTopicConfig())
    acts: ActsConfig = field(default_factory=lambda: ActsConfig())
    tag_extraction: TagExtractionConfig = field(
        default_factory=lambda: TagExtractionConfig()
    )
    llm_summary: LLMSummaryConfig = field(default_factory=lambda: LLMSummaryConfig())
    llm_speaker_summary: LLMSpeakerSummaryConfig = field(
        default_factory=lambda: LLMSpeakerSummaryConfig()
    )
    llm_action_items: LLMActionItemsConfig = field(
        default_factory=lambda: LLMActionItemsConfig()
    )
    llm_custom_qa: "LLMCustomQAConfig" = field(
        default_factory=lambda: LLMCustomQAConfig()
    )
    ui_presets: "AnalysisUiPresetsConfig" = field(
        default_factory=lambda: AnalysisUiPresetsConfig()
    )
    group_llm_synthesis: "GroupLLMSynthesisConfig" = field(
        default_factory=lambda: GroupLLMSynthesisConfig()
    )
    chart_descriptions: "ChartDescriptionsConfig" = field(
        default_factory=lambda: ChartDescriptionsConfig()
    )
    qa_analysis: QAAnalysisConfig = field(default_factory=lambda: QAAnalysisConfig())
    temporal_dynamics: TemporalDynamicsConfig = field(
        default_factory=lambda: TemporalDynamicsConfig()
    )
    pauses: PausesConfig = field(default_factory=lambda: PausesConfig())
    transcript_quality: "TranscriptQualityConfig" = field(
        default_factory=lambda: TranscriptQualityConfig()
    )
    epistemic_markers: "EpistemicMarkersConfig" = field(
        default_factory=lambda: EpistemicMarkersConfig()
    )
    names: "NamesConfig" = field(default_factory=lambda: NamesConfig())
    keyphrases: "KeyphrasesConfig" = field(default_factory=lambda: KeyphrasesConfig())
    politeness: "PolitenessConfig" = field(default_factory=lambda: PolitenessConfig())
    topic_shift: "TopicShiftConfig" = field(default_factory=lambda: TopicShiftConfig())
    echoes: EchoesConfig = field(default_factory=lambda: EchoesConfig())
    momentum: MomentumConfig = field(default_factory=lambda: MomentumConfig())
    moments: MomentsConfig = field(default_factory=lambda: MomentsConfig())
    vectorization: VectorizationConfig = field(
        default_factory=lambda: VectorizationConfig()
    )
    voice: VoiceConfig = field(default_factory=lambda: VoiceConfig())
    affect_tension: AffectTensionConfig = field(
        default_factory=lambda: AffectTensionConfig()
    )
    emotion: EmotionLexicalConfig = field(
        default_factory=lambda: EmotionLexicalConfig()
    )
    contextual_emotion: ContextualEmotionConfig = field(
        default_factory=lambda: ContextualEmotionConfig()
    )
    fine_grained_emotion: FineGrainedEmotionConfig = field(
        default_factory=lambda: FineGrainedEmotionConfig()
    )

    # Profile management - active profiles for each module
    active_topic_modeling_profile: str = "default"
    active_acts_profile: str = "default"
    active_tag_extraction_profile: str = "default"
    active_qa_analysis_profile: str = "default"
    active_temporal_dynamics_profile: str = "default"
    active_vectorization_profile: str = "default"

    def __post_init__(self) -> None:
        # Flat analysis_* pilot slices (fixed order).
        from transcriptx.core.config.models.analysis_sentiment import (
            AnalysisSentimentSettingsModel,
        )
        from transcriptx.core.config.models.analysis_ner import (
            AnalysisNerSettingsModel,
        )
        from transcriptx.core.config.models.analysis_wordcloud import (
            AnalysisWordcloudSettingsModel,
        )
        from transcriptx.core.config.models.analysis_speakers import (
            AnalysisSpeakersSettingsModel,
        )
        from transcriptx.core.config.models.analysis_interaction import (
            AnalysisInteractionSettingsModel,
        )
        from transcriptx.core.config.models.analysis_entity import (
            AnalysisEntitySettingsModel,
        )
        from transcriptx.core.config.models.analysis_legacy_semantic import (
            AnalysisLegacySemanticSettingsModel,
        )
        from transcriptx.core.config.models.quality_filtering_profiles import (
            QualityFilteringProfilesSettingsModel,
        )
        from transcriptx.core.config.models.semantic_similarity_profiles import (
            SemanticSimilarityProfilesSettingsModel,
        )
        from transcriptx.core.config.models.quick_analysis_settings import (
            QuickAnalysisSettingsModel,
        )
        from transcriptx.core.config.models.full_analysis_settings import (
            FullAnalysisSettingsModel,
        )

        _hydrate_analysis_slice(self, AnalysisSentimentSettingsModel())
        _hydrate_analysis_slice(self, AnalysisNerSettingsModel())
        _hydrate_analysis_slice(self, AnalysisWordcloudSettingsModel())
        _hydrate_analysis_slice(self, AnalysisSpeakersSettingsModel())
        _hydrate_analysis_slice(self, AnalysisInteractionSettingsModel())
        _hydrate_analysis_slice(self, AnalysisEntitySettingsModel())
        _hydrate_analysis_slice(self, AnalysisLegacySemanticSettingsModel())
        _hydrate_mapping_store(
            self, "quality_filtering_profiles", QualityFilteringProfilesSettingsModel()
        )
        _hydrate_mapping_store(
            self,
            "semantic_similarity_profiles",
            SemanticSimilarityProfilesSettingsModel(),
        )
        _hydrate_mapping_store(
            self, "quick_analysis_settings", QuickAnalysisSettingsModel()
        )
        _hydrate_mapping_store(
            self, "full_analysis_settings", FullAnalysisSettingsModel()
        )
