"""Analysis configuration classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


def _dataclass_from_nested_dump(cls: type, data: dict[str, Any]) -> object:
    """Build a nested dataclass instance from a model_dump() dict (no __init__)."""
    from dataclasses import is_dataclass
    from typing import get_type_hints

    instance = object.__new__(cls)
    annotations = get_type_hints(cls)
    for key, value in data.items():
        field_type = annotations.get(key)
        if (
            isinstance(value, dict)
            and field_type is not None
            and is_dataclass(field_type)
        ):
            object.__setattr__(
                instance, key, _dataclass_from_nested_dump(field_type, value)
            )
        else:
            object.__setattr__(instance, key, value)
    return instance


def _hydrate_dataclass_from_pydantic(instance: object, model: BaseModel) -> None:
    """Populate dataclass fields from a Pydantic model defaults dump (no revalidation).

    Nested dict values are reconstructed as nested dataclass instances when the
    corresponding field annotation is a dataclass type (needed for summary /
    highlights attribute access and file-override merge).
    """
    from dataclasses import is_dataclass
    from typing import get_type_hints

    annotations = get_type_hints(type(instance))
    for key, value in model.model_dump().items():
        field_type = annotations.get(key)
        if (
            isinstance(value, dict)
            and field_type is not None
            and is_dataclass(field_type)
        ):
            object.__setattr__(
                instance, key, _dataclass_from_nested_dump(field_type, value)
            )
        else:
            object.__setattr__(instance, key, value)


def _hydrate_analysis_slice(instance: object, model: BaseModel) -> None:
    """Hydrate only the fields owned by a partial analysis_* pilot model."""
    from dataclasses import is_dataclass
    from typing import get_type_hints

    annotations = get_type_hints(type(instance))
    for key, value in model.model_dump().items():
        field_type = annotations.get(key)
        if (
            isinstance(value, dict)
            and field_type is not None
            and is_dataclass(field_type)
        ):
            object.__setattr__(
                instance, key, _dataclass_from_nested_dump(field_type, value)
            )
        else:
            object.__setattr__(instance, key, value)


def _hydrate_mapping_store(instance: object, attr_name: str, model: BaseModel) -> None:
    """Set one AnalysisConfig mapping attribute from a fresh model_dump()."""
    object.__setattr__(instance, attr_name, model.model_dump())


@dataclass
class CorrectionsLlmConfig:
    """Nested LLM settings for Corrections Studio. Defaults from CorrectionsLlmSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    effort: str = field(init=False, repr=True)
    request_timeout_seconds: float = field(init=False, repr=True)
    total_wall_clock_seconds: float = field(init=False, repr=True)
    max_chunks: int = field(init=False, repr=True)
    chunk_max_segments: int = field(init=False, repr=True)
    chunk_overlap_segments: int = field(init=False, repr=True)
    max_candidates_per_chunk: int = field(init=False, repr=True)
    max_candidates_per_transcript: int = field(init=False, repr=True)
    continue_on_failure: bool = field(init=False, repr=True)
    assess_deterministic: bool = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.corrections_llm import (
            CorrectionsLlmSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, CorrectionsLlmSettingsModel())


@dataclass
class CorrectionsConfig:
    """Configuration for transcript corrections. Defaults owned by CorrectionsSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    interactive_review: bool = field(init=False, repr=True)
    consistency_similarity_threshold: float = field(init=False, repr=True)
    fuzzy_similarity_threshold: float = field(init=False, repr=True)
    known_acronyms: list[str] = field(init=False, repr=True)
    known_org_phrases: dict[str, list[str]] = field(init=False, repr=True)
    write_csv_summary: bool = field(init=False, repr=True)
    store_corrected_transcript: bool = field(init=False, repr=True)
    default_rule_scope: str = field(init=False, repr=True)
    enable_fuzzy: bool = field(init=False, repr=True)
    update_original_file: bool = field(init=False, repr=True)
    create_backup: bool = field(init=False, repr=True)
    llm: CorrectionsLlmConfig = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.corrections import CorrectionsSettingsModel

        _hydrate_dataclass_from_pydantic(self, CorrectionsSettingsModel())


@dataclass
class SpeakerExemplarsConfig:
    """Configuration for speaker exemplars. Defaults owned by SpeakerExemplarsSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    count: int = field(init=False, repr=True)
    min_words: int = field(init=False, repr=True)
    max_words: int = field(init=False, repr=True)
    max_segments_considered: int = field(init=False, repr=True)
    merge_adjacent: bool = field(init=False, repr=True)
    dedupe: bool = field(init=False, repr=True)
    near_dedupe: bool = field(init=False, repr=True)
    near_dedupe_threshold: float = field(init=False, repr=True)
    near_dedupe_max_checks: int = field(init=False, repr=True)
    methods_enabled: dict[str, bool] = field(init=False, repr=True)
    weights: dict[str, float] = field(init=False, repr=True)
    distinctive_scope: str = field(init=False, repr=True)
    distinctive_min_other_segments: int = field(init=False, repr=True)
    distinctive_max_other_speakers: int = field(init=False, repr=True)
    distinctive_max_other_segments_total: int = field(init=False, repr=True)
    distinctive_max_other_segments_per_speaker: int = field(init=False, repr=True)
    tfidf_max_features: int = field(init=False, repr=True)
    tfidf_ngram_range: tuple[int, int] = field(init=False, repr=True)
    length_prior_enabled: bool = field(init=False, repr=True)
    length_prior_center: float = field(init=False, repr=True)
    length_prior_sigma: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.speaker_exemplars import (
            SpeakerExemplarsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, SpeakerExemplarsSettingsModel())


@dataclass
class HighlightsCounts:
    cold_open_quotes: int = field(init=False, repr=True)
    total_highlights: int = field(init=False, repr=True)
    conflict_windows: int = field(init=False, repr=True)
    emblematic_phrases: int = field(init=False, repr=True)


@dataclass
class HighlightsThresholds:
    conflict_spike_percentile: float = field(init=False, repr=True)
    min_gap_seconds: float = field(init=False, repr=True)
    min_quote_words: int = field(init=False, repr=True)
    max_quote_words: int = field(init=False, repr=True)
    max_consecutive_per_speaker: int = field(init=False, repr=True)
    min_phrase_len: int = field(init=False, repr=True)
    max_phrase_len: int = field(init=False, repr=True)
    min_phrase_frequency: int = field(init=False, repr=True)


@dataclass
class HighlightsWeights:
    intensity: float = field(init=False, repr=True)
    conflict: float = field(init=False, repr=True)
    uniqueness: float = field(init=False, repr=True)
    keyword_richness: float = field(init=False, repr=True)
    content_density: float = field(init=False, repr=True)


@dataclass
class HighlightsSections:
    cold_open_enabled: bool = field(init=False, repr=True)
    conflict_points_enabled: bool = field(init=False, repr=True)
    emblematic_phrases_enabled: bool = field(init=False, repr=True)


@dataclass
class HighlightsOutput:
    write_conflict_csv: bool = field(init=False, repr=True)


@dataclass
class HighlightsMergeAdjacent:
    enabled: bool = field(init=False, repr=True)
    max_gap_seconds: float = field(init=False, repr=True)
    max_segments: int = field(init=False, repr=True)


@dataclass
class HighlightsConflict:
    window_seconds: float = field(init=False, repr=True)
    step_seconds: float = field(init=False, repr=True)
    merge_gap_seconds: float = field(init=False, repr=True)


@dataclass
class HighlightsColdOpen:
    window_seconds: float = field(init=False, repr=True)
    window_policy: str = field(init=False, repr=True)


@dataclass
class HighlightsConfig:
    """Configuration for highlights. Defaults owned by HighlightsSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    counts: HighlightsCounts = field(init=False, repr=True)
    thresholds: HighlightsThresholds = field(init=False, repr=True)
    weights: HighlightsWeights = field(init=False, repr=True)
    sections: HighlightsSections = field(init=False, repr=True)
    output: HighlightsOutput = field(init=False, repr=True)
    merge_adjacent: HighlightsMergeAdjacent = field(init=False, repr=True)
    conflict: HighlightsConflict = field(init=False, repr=True)
    cold_open: HighlightsColdOpen = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.highlights import HighlightsSettingsModel

        _hydrate_dataclass_from_pydantic(self, HighlightsSettingsModel())


@dataclass
class SummaryCounts:
    theme_bullets: int = field(init=False, repr=True)
    tension_bullets: int = field(init=False, repr=True)
    commitments: int = field(init=False, repr=True)


@dataclass
class SummarySections:
    overview_enabled: bool = field(init=False, repr=True)
    key_themes_enabled: bool = field(init=False, repr=True)
    tension_points_enabled: bool = field(init=False, repr=True)
    commitments_enabled: bool = field(init=False, repr=True)


@dataclass
class SummaryCommitments:
    rules: list[str] = field(init=False, repr=True)
    max_per_owner: int = field(init=False, repr=True)


@dataclass
class SummaryConfig:
    """Configuration for summary. Defaults owned by SummarySettingsModel."""

    enabled: bool = field(init=False, repr=True)
    require_highlights: bool = field(init=False, repr=True)
    compute_highlights_if_missing: bool = field(init=False, repr=True)
    allow_degraded: bool = field(init=False, repr=True)
    counts: SummaryCounts = field(init=False, repr=True)
    sections: SummarySections = field(init=False, repr=True)
    commitments: SummaryCommitments = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.summary import SummarySettingsModel

        _hydrate_dataclass_from_pydantic(self, SummarySettingsModel())


@dataclass
class BERTopicConfig:
    """Configuration for BERTopic. Defaults owned by BERTopicSettingsModel."""

    embedding_model: str = field(init=False, repr=True)
    min_topic_size: int = field(init=False, repr=True)
    nr_topics: str = field(init=False, repr=True)
    top_n_words: int = field(init=False, repr=True)
    label_words: int = field(init=False, repr=True)
    calculate_probabilities: bool = field(init=False, repr=True)
    timeout_seconds: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.bertopic import (
            BERTopicSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, BERTopicSettingsModel())


@dataclass
class SemanticSimilarityV2Config:
    """Tunable settings for semantic_similarity_v2. Defaults owned by SemanticSimilarityV2SettingsModel."""

    enabled: bool = field(init=False, repr=True)
    mode: str = field(init=False, repr=True)
    model_name: str = field(init=False, repr=True)
    batch_size: int = field(init=False, repr=True)
    min_text_length_words: int = field(init=False, repr=True)
    self_similarity_threshold: float = field(init=False, repr=True)
    cross_speaker_similarity_threshold: float = field(init=False, repr=True)
    self_time_window_seconds: float = field(init=False, repr=True)
    cross_speaker_time_window_seconds: float = field(init=False, repr=True)
    max_candidate_pairs: int = field(init=False, repr=True)
    top_k_per_segment: int = field(init=False, repr=True)
    timeout_seconds: float = field(init=False, repr=True)
    persist_embeddings: bool = field(init=False, repr=True)
    lru_size: int = field(init=False, repr=True)
    use_lexical_prefilter: bool = field(init=False, repr=True)
    lexical_prefilter_min_jaccard: float = field(init=False, repr=True)
    strict_advanced_inputs: bool = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.semantic_similarity_v2 import (
            SemanticSimilarityV2SettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, SemanticSimilarityV2SettingsModel())


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

    # Corrections settings
    corrections: CorrectionsConfig = field(default_factory=CorrectionsConfig)

    # Speaker exemplars settings
    speaker_exemplars: SpeakerExemplarsConfig = field(
        default_factory=SpeakerExemplarsConfig
    )

    # Highlights and summary settings
    highlights: HighlightsConfig = field(default_factory=HighlightsConfig)
    summary: SummaryConfig = field(default_factory=SummaryConfig)

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
    semantic_similarity_v2: SemanticSimilarityV2Config = field(
        default_factory=SemanticSimilarityV2Config
    )
    active_semantic_similarity_v2_profile: str = "balanced_v2"
    semantic_similarity_v2_profiles: dict[str, dict[str, Any]] = field(
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
        from transcriptx.core.config.models.semantic_similarity_v2_profiles import (
            SemanticSimilarityV2ProfilesSettingsModel,
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
        _hydrate_analysis_slice(self, AnalysisInteractionSettingsModel())
        _hydrate_analysis_slice(self, AnalysisEntitySettingsModel())
        _hydrate_analysis_slice(self, AnalysisLegacySemanticSettingsModel())
        _hydrate_mapping_store(
            self, "quality_filtering_profiles", QualityFilteringProfilesSettingsModel()
        )
        _hydrate_mapping_store(
            self,
            "semantic_similarity_v2_profiles",
            SemanticSimilarityV2ProfilesSettingsModel(),
        )
        _hydrate_mapping_store(
            self, "quick_analysis_settings", QuickAnalysisSettingsModel()
        )
        _hydrate_mapping_store(
            self, "full_analysis_settings", FullAnalysisSettingsModel()
        )


@dataclass
class TopicModelingConfig:
    """Configuration for topic modeling. Defaults owned by TopicModelingSettingsModel."""

    max_features: int = field(init=False, repr=True)
    min_df: int = field(init=False, repr=True)
    max_df: float = field(init=False, repr=True)
    ngram_range: tuple[int, int] = field(init=False, repr=True)
    random_state: int = field(init=False, repr=True)
    max_iter_lda: int = field(init=False, repr=True)
    max_iter_nmf: int = field(init=False, repr=True)
    alpha_H: float = field(init=False, repr=True)
    tol: float = field(init=False, repr=True)
    learning_method: str = field(init=False, repr=True)
    k_range: tuple[int, int] = field(init=False, repr=True)
    test_size: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.topic_modeling import (
            TopicModelingSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, TopicModelingSettingsModel())


@dataclass
class ActsConfig:
    """Configuration for dialogue acts. Defaults owned by ActsSettingsModel."""

    method: str = field(init=False, repr=True)
    use_context: bool = field(init=False, repr=True)
    context_window_size: int = field(init=False, repr=True)
    context_window_type: str = field(init=False, repr=True)
    include_speaker_info: bool = field(init=False, repr=True)
    include_timing_info: bool = field(init=False, repr=True)
    min_confidence: float = field(init=False, repr=True)
    high_confidence_threshold: float = field(init=False, repr=True)
    ensemble_weight_transformer: float = field(init=False, repr=True)
    ensemble_weight_ml: float = field(init=False, repr=True)
    ensemble_weight_rules: float = field(init=False, repr=True)
    ml_model_name: str = field(init=False, repr=True)
    ml_use_gpu: bool = field(init=False, repr=True)
    ml_batch_size: int = field(init=False, repr=True)
    ml_max_length: int = field(init=False, repr=True)
    rules_use_enhanced_patterns: bool = field(init=False, repr=True)
    rules_use_fallback_logic: bool = field(init=False, repr=True)
    rules_confidence_boost_exact_match: float = field(init=False, repr=True)
    rules_context_boost_factor: float = field(init=False, repr=True)
    enable_caching: bool = field(init=False, repr=True)
    cache_size: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.acts import (
            ActsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, ActsSettingsModel())


@dataclass
class TagExtractionConfig:
    """Configuration for tag extraction. Defaults owned by TagExtractionSettingsModel."""

    early_window_seconds: int = field(init=False, repr=True)
    early_segments: int = field(init=False, repr=True)
    min_confidence: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.tag_extraction import (
            TagExtractionSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, TagExtractionSettingsModel())


@dataclass
class LLMSummaryConfig:
    """Configuration for llm_summary. Defaults owned by LLMSummarySettingsModel."""

    effort: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.llm_summary import LLMSummarySettingsModel

        _hydrate_dataclass_from_pydantic(self, LLMSummarySettingsModel())


@dataclass
class LLMSpeakerSummaryConfig:
    """Defaults owned by LLMSpeakerSummarySettingsModel."""

    effort: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.llm_speaker_summary import (
            LLMSpeakerSummarySettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, LLMSpeakerSummarySettingsModel())


@dataclass
class LLMActionItemsConfig:
    """Defaults owned by LLMActionItemsSettingsModel."""

    effort: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.llm_action_items import (
            LLMActionItemsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, LLMActionItemsSettingsModel())


@dataclass
class GroupLLMSynthesisConfig:
    """Defaults owned by GroupLLMSynthesisSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    effort: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.group_llm_synthesis import (
            GroupLLMSynthesisSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, GroupLLMSynthesisSettingsModel())


@dataclass
class ChartDescriptionsConfig:
    """Defaults owned by ChartDescriptionsSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    chart_set: str = field(init=False, repr=True)
    max_description_chars: int = field(init=False, repr=True)
    request_timeout: float = field(init=False, repr=True)
    max_retries: int = field(init=False, repr=True)
    circuit_breaker_failures: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.chart_descriptions import (
            ChartDescriptionsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, ChartDescriptionsSettingsModel())


@dataclass
class QAAnalysisConfig:
    """Configuration for Q&A analysis. Defaults owned by QAAnalysisSettingsModel."""

    response_time_threshold: float = field(init=False, repr=True)
    weight_directness: float = field(init=False, repr=True)
    weight_completeness: float = field(init=False, repr=True)
    weight_relevance: float = field(init=False, repr=True)
    weight_length: float = field(init=False, repr=True)
    min_match_threshold: float = field(init=False, repr=True)
    good_match_threshold: float = field(init=False, repr=True)
    high_match_threshold: float = field(init=False, repr=True)
    min_answer_length: int = field(init=False, repr=True)
    optimal_answer_length: int = field(init=False, repr=True)
    max_answer_length: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.qa_analysis import (
            QAAnalysisSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, QAAnalysisSettingsModel())


@dataclass
class TemporalDynamicsConfig:
    """Configuration for temporal dynamics. Defaults owned by TemporalDynamicsSettingsModel."""

    window_size: float = field(init=False, repr=True)
    weight_segment_factor: float = field(init=False, repr=True)
    weight_length_factor: float = field(init=False, repr=True)
    weight_question_factor: float = field(init=False, repr=True)
    max_segments_normalization: float = field(init=False, repr=True)
    max_questions_normalization: float = field(init=False, repr=True)
    opening_phase_percentage: float = field(init=False, repr=True)
    opening_phase_max_seconds: float = field(init=False, repr=True)
    closing_phase_percentage: float = field(init=False, repr=True)
    closing_phase_max_seconds: float = field(init=False, repr=True)
    sentiment_change_threshold: float = field(init=False, repr=True)
    engagement_change_threshold: float = field(init=False, repr=True)
    speaking_rate_change_threshold: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.temporal_dynamics import (
            TemporalDynamicsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, TemporalDynamicsSettingsModel())


@dataclass
class AffectTensionConfig:
    """Configuration for affect_tension. Defaults owned by AffectTensionSettingsModel."""

    mismatch_compound_threshold: float = field(init=False, repr=True)
    trust_like_threshold: float = field(init=False, repr=True)
    pos_emotion_threshold: float = field(init=False, repr=True)
    weight_posneg_mismatch: float = field(init=False, repr=True)
    weight_trust_neutral: float = field(init=False, repr=True)
    weight_entropy: float = field(init=False, repr=True)
    weight_volatility: float = field(init=False, repr=True)
    window_segments: int = field(init=False, repr=True)
    window_seconds: float | None = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.affect_tension import (
            AffectTensionSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, AffectTensionSettingsModel())


@dataclass
class EmotionLexicalConfig:
    """analysis.emotion.* lexical settings."""

    low_coverage_threshold: float = field(init=False, repr=True)
    no_hit_rate_warn: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.analysis_emotion_family import (
            EmotionLexicalSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, EmotionLexicalSettingsModel())


@dataclass
class ContextualEmotionConfig:
    """analysis.contextual_emotion.* experimental classifier settings."""

    profile_id: str = field(init=False, repr=True)
    confidence_threshold: float = field(init=False, repr=True)
    batch_size: int = field(init=False, repr=True)
    release_channel: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.analysis_emotion_family import (
            ContextualEmotionSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, ContextualEmotionSettingsModel())


@dataclass
class FineGrainedEmotionConfig:
    """analysis.fine_grained_emotion.* experimental multilabel settings."""

    profile_id: str = field(init=False, repr=True)
    label_threshold: float = field(init=False, repr=True)
    max_labels_per_segment: int = field(init=False, repr=True)
    batch_size: int = field(init=False, repr=True)
    release_channel: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.analysis_emotion_family import (
            FineGrainedEmotionSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, FineGrainedEmotionSettingsModel())


@dataclass
class PausesConfig:
    """Configuration for pauses analysis. Defaults owned by PausesSettingsModel."""

    min_long_pause_seconds: float = field(init=False, repr=True)
    post_question_multiplier: float = field(init=False, repr=True)
    percentile_long_pause: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.pauses import PausesSettingsModel

        _hydrate_dataclass_from_pydantic(self, PausesSettingsModel())


@dataclass
class TranscriptQualityConfig:
    """ASR confidence settings. Defaults owned by TranscriptQualitySettingsModel."""

    low_score_threshold: float = field(init=False, repr=True)
    max_gap_seconds: float = field(init=False, repr=True)
    cluster_merge_seconds: float = field(init=False, repr=True)
    max_spans: int = field(init=False, repr=True)
    max_clusters: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.transcript_quality import (
            TranscriptQualitySettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, TranscriptQualitySettingsModel())


@dataclass
class EchoesConfig:
    """Configuration for echoes. Defaults owned by EchoesSettingsModel."""

    lookback_seconds: float = field(init=False, repr=True)
    max_candidates: int = field(init=False, repr=True)
    explicit_quote_weight: float = field(init=False, repr=True)
    lexical_echo_threshold: float = field(init=False, repr=True)
    paraphrase_threshold: float = field(init=False, repr=True)
    min_tokens: int = field(init=False, repr=True)
    exclude_phrases: list[str] = field(init=False, repr=True)
    enable_semantic_paraphrase: bool = field(init=False, repr=True)
    semantic_model_name: str | None = field(init=False, repr=True)
    echo_burst_window_seconds: float = field(init=False, repr=True)
    echo_burst_min_events: int = field(init=False, repr=True)
    echo_burst_percentile_threshold: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.echoes import (
            EchoesSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, EchoesSettingsModel())


@dataclass
class MomentumConfig:
    """Configuration for momentum. Defaults owned by MomentumSettingsModel."""

    window_length_seconds: float = field(init=False, repr=True)
    window_step_seconds: float = field(init=False, repr=True)
    stall_threshold_percentile: float = field(init=False, repr=True)
    min_stall_duration_seconds: float = field(init=False, repr=True)
    momentum_cliff_threshold: float = field(init=False, repr=True)
    novelty_lookback_windows: int = field(init=False, repr=True)
    weights: dict[str, float] = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.momentum import (
            MomentumSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, MomentumSettingsModel())


@dataclass
class MomentsConfig:
    """Configuration for moments. Defaults owned by MomentsSettingsModel."""

    top_n: int = field(init=False, repr=True)
    merge_seconds: float = field(init=False, repr=True)
    weight_map: dict[str, float] = field(init=False, repr=True)
    diversity_bonus: float = field(init=False, repr=True)
    multi_speaker_bonus: float = field(init=False, repr=True)
    write_markdown: bool = field(init=False, repr=True)
    excerpt_max_chars: int = field(init=False, repr=True)
    excerpt_max_segments: int = field(init=False, repr=True)
    max_span_seconds: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.moments import (
            MomentsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, MomentsSettingsModel())


@dataclass
class VectorizationConfig:
    """Shared vectorization config. Defaults owned by VectorizationSettingsModel."""

    max_features: int = field(init=False, repr=True)
    min_df: int = field(init=False, repr=True)
    max_df: float = field(init=False, repr=True)
    ngram_range: tuple[int, int] = field(init=False, repr=True)
    wordcloud_max_features: int = field(init=False, repr=True)
    wordcloud_ngram_range: tuple[int, int] = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.vectorization import (
            VectorizationSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, VectorizationSettingsModel())


@dataclass
class VoiceConfig:
    """Configuration for voice modality analysis (CPU-first).

    Defaults owned by VoiceSettingsModel.
    """

    enabled: bool = field(init=False, repr=True)
    sample_rate: int = field(init=False, repr=True)
    vad_mode: int = field(init=False, repr=True)
    pad_s: float = field(init=False, repr=True)
    max_seconds_for_pitch: float = field(init=False, repr=True)
    max_segments_considered: int | None = field(init=False, repr=True)
    egemaps_enabled: bool = field(init=False, repr=True)
    deep_mode: bool = field(init=False, repr=True)
    deep_model_name: str = field(init=False, repr=True)
    deep_max_seconds: float = field(init=False, repr=True)
    store_parquet: str = field(init=False, repr=True)
    strict_audio_hash: bool = field(init=False, repr=True)
    mismatch_threshold: float = field(init=False, repr=True)
    top_k_moments: int = field(init=False, repr=True)
    drift_threshold: float = field(init=False, repr=True)
    bin_seconds: float = field(init=False, repr=True)
    smoothing_alpha: float = field(init=False, repr=True)
    include_unnamed_in_global_curves: bool = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.voice import VoiceSettingsModel

        _hydrate_dataclass_from_pydantic(self, VoiceSettingsModel())
