"""Analysis configuration classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from .base import DEFAULT_NER_LABELS, DEFAULT_STOPWORDS


@dataclass
class CorrectionsConfig:
    enabled: bool = True
    interactive_review: bool = True
    consistency_similarity_threshold: float = 0.88
    fuzzy_similarity_threshold: float = 0.92
    known_acronyms: list[str] = field(default_factory=lambda: ["CSE", "REN21"])
    known_org_phrases: dict[str, list[str]] = field(
        default_factory=lambda: {"REN21": ["ren twenty one", "wren twenty one"]}
    )
    write_csv_summary: bool = True
    store_corrected_transcript: bool = True
    default_rule_scope: str = "project"
    enable_fuzzy: bool = False
    update_original_file: bool = False
    create_backup: bool = True


@dataclass
class SpeakerExemplarsConfig:
    """Configuration for speaker exemplars on-demand analysis."""

    enabled: bool = True
    count: int = 10
    min_words: int = 3
    max_words: int = 80
    max_segments_considered: int = 2000
    merge_adjacent: bool = True

    dedupe: bool = True
    near_dedupe: bool = False
    near_dedupe_threshold: float = 0.85
    near_dedupe_max_checks: int = 200

    methods_enabled: dict[str, bool] = field(
        default_factory=lambda: {
            "unique": True,
            "tfidf_within_speaker": True,
            "distinctive_vs_others": True,
        }
    )
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "unique": 0.34,
            "tfidf_within_speaker": 0.33,
            "distinctive_vs_others": 0.33,
        }
    )

    distinctive_scope: str = "transcript"
    distinctive_min_other_segments: int = 50
    distinctive_max_other_speakers: int = 6
    distinctive_max_other_segments_total: int = 2000
    distinctive_max_other_segments_per_speaker: int = 400

    tfidf_max_features: int = 1000
    tfidf_ngram_range: tuple[int, int] = (1, 2)

    length_prior_enabled: bool = True
    length_prior_center: float = 18.0
    length_prior_sigma: float = 12.0


@dataclass
class HighlightsCounts:
    cold_open_quotes: int = 5
    total_highlights: int = 15
    conflict_windows: int = 6
    emblematic_phrases: int = 12


@dataclass
class HighlightsThresholds:
    conflict_spike_percentile: float = 95.0
    min_gap_seconds: float = 30.0
    min_quote_words: int = 4
    max_quote_words: int = 60
    max_consecutive_per_speaker: int = 2
    min_phrase_len: int = 2
    max_phrase_len: int = 5
    min_phrase_frequency: int = 3


@dataclass
class HighlightsWeights:
    intensity: float = 0.40
    conflict: float = 0.30
    uniqueness: float = 0.20
    keyword_richness: float = 0.10


@dataclass
class HighlightsSections:
    cold_open_enabled: bool = True
    conflict_points_enabled: bool = True
    emblematic_phrases_enabled: bool = True


@dataclass
class HighlightsOutput:
    write_conflict_csv: bool = False


@dataclass
class HighlightsMergeAdjacent:
    enabled: bool = True
    max_gap_seconds: float = 1.0
    max_segments: int = 3


@dataclass
class HighlightsConflict:
    window_seconds: float = 30.0
    step_seconds: float = 10.0
    merge_gap_seconds: float = 10.0


@dataclass
class HighlightsColdOpen:
    window_seconds: float = 90.0
    window_policy: str = "seconds"  # "seconds" or "segments"


@dataclass
class HighlightsConfig:
    enabled: bool = True
    counts: HighlightsCounts = field(default_factory=HighlightsCounts)
    thresholds: HighlightsThresholds = field(default_factory=HighlightsThresholds)
    weights: HighlightsWeights = field(default_factory=HighlightsWeights)
    sections: HighlightsSections = field(default_factory=HighlightsSections)
    output: HighlightsOutput = field(default_factory=HighlightsOutput)
    merge_adjacent: HighlightsMergeAdjacent = field(
        default_factory=HighlightsMergeAdjacent
    )
    conflict: HighlightsConflict = field(default_factory=HighlightsConflict)
    cold_open: HighlightsColdOpen = field(default_factory=HighlightsColdOpen)


@dataclass
class SummaryCounts:
    theme_bullets: int = 6
    tension_bullets: int = 5
    commitments: int = 8


@dataclass
class SummarySections:
    overview_enabled: bool = True
    key_themes_enabled: bool = True
    tension_points_enabled: bool = True
    commitments_enabled: bool = True


@dataclass
class SummaryCommitments:
    rules: list[str] = field(
        default_factory=lambda: [
            r"\b(I|we)\s+(will|can|shall|need to|have to)\s+.+",
            r"\b(let's|lets)\s+.+",
            r"\b(action item|to-do|next step)\b.+",
        ]
    )
    max_per_owner: int = 3


@dataclass
class SummaryConfig:
    enabled: bool = True
    require_highlights: bool = False
    compute_highlights_if_missing: bool = True
    allow_degraded: bool = False
    counts: SummaryCounts = field(default_factory=SummaryCounts)
    sections: SummarySections = field(default_factory=SummarySections)
    commitments: SummaryCommitments = field(default_factory=SummaryCommitments)


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
    sentiment_window_size: int = 10
    sentiment_min_confidence: float = 0.1

    # Emotion analysis settings
    # Control the emotion detection model and confidence thresholds
    emotion_min_confidence: float = 0.3
    emotion_model_name: str = "bhadresh-savani/distilbert-base-uncased-emotion"
    emotion_output_mode: str = "top1"  # "top1" | "multilabel"
    emotion_score_threshold: float = 0.30  # for multilabel: keep labels above this

    # Sentiment analysis backend
    sentiment_backend: str = "vader"  # "vader" | "transformers"
    sentiment_model_name: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"

    # NER analysis settings
    # Control which entities to extract and how to process them
    ner_labels: list[str] = field(default_factory=lambda: DEFAULT_NER_LABELS)
    ner_min_confidence: float = 0.5
    ner_include_geocoding: bool = True
    ner_use_light_model: bool = False
    ner_max_segments: int = 5000
    ner_batch_size: int = 100

    # Word clouds settings
    # Control the generation and appearance of word clouds
    wordcloud_max_words: int = 100
    wordcloud_min_font_size: int = 8
    wordcloud_stopwords: list[str] = field(default_factory=lambda: DEFAULT_STOPWORDS)
    # When True, per-speaker charts/data only for named speakers
    exclude_unidentified_from_speaker_charts: bool = True

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
    readability_metrics: list[str] = field(
        default_factory=lambda: [
            "flesch_reading_ease",
            "flesch_kincaid_grade",
            "gunning_fog",
        ]
    )

    # Speaker interactions analysis settings (unified networks + interruptions)
    # Control how speaker interactions are detected and analyzed
    interaction_overlap_threshold: float = 0.5  # seconds
    interaction_min_gap: float = 0.1  # seconds
    interaction_min_segment_length: float = 0.5  # seconds
    interaction_response_threshold: float = 2.0  # seconds
    interaction_include_responses: bool = True
    interaction_include_overlaps: bool = True
    interaction_min_interactions: int = 2
    interaction_time_window: float = 30.0  # seconds

    # Entity sentiment analysis settings
    # Control how entity-focused sentiment analysis works
    entity_min_mentions: int = 2
    entity_types: list[str] = field(
        default_factory=lambda: ["PERSON", "ORG", "GPE", "LOC"]
    )
    entity_sentiment_threshold: float = (
        0.05  # Minimum sentiment difference to consider significant
    )

    # Conversation loop detection settings
    # Control how conversation patterns and loops are identified
    loop_max_intermediate_turns: int = 2
    loop_exclude_monologues: bool = True
    loop_min_gap: float = 0.1  # seconds
    loop_max_gap: float = 10.0  # seconds

    # Semantic similarity and repetition detection settings
    # Control how semantic similarity analysis and repetition detection work
    semantic_similarity_threshold: float = (
        0.7  # Threshold for within-speaker repetition detection
    )
    cross_speaker_similarity_threshold: float = (
        0.6  # Threshold for cross-speaker similarity
    )
    repetition_time_window: float = (
        300.0  # 5 minutes - time window for repetition detection
    )
    cross_speaker_time_window: float = (
        600.0  # 10 minutes - time window for cross-speaker analysis
    )
    semantic_model_name: str = (
        "sentence-transformers/all-MiniLM-L6-v2"  # Model for semantic similarity
    )
    clustering_eps: float = 0.3  # DBSCAN epsilon for repetition clustering
    clustering_min_samples: int = 2  # DBSCAN min_samples for repetition clustering

    # Performance limits for semantic similarity (to prevent hanging)
    # These settings help prevent the system from processing too much data
    max_segments_for_semantic: int = 1000  # Maximum segments to process
    max_segments_per_speaker: int = (
        200  # Maximum segments per speaker for repetition detection
    )
    max_segments_for_cross_speaker: int = (
        500  # Maximum segments for cross-speaker repetition detection
    )
    use_quality_filtering: bool = (
        True  # Use quality-based filtering instead of simple truncation
    )
    min_segment_quality_score: float = 0.0  # Minimum quality score for segments

    # Quality filtering profile system
    # Different profiles optimize for different types of conversations
    quality_filtering_profile: str = "balanced"  # Profile to use
    semantic_similarity_method: str = "simple"  # "simple" or "advanced"
    quality_filtering_profiles: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "balanced": {
                "description": "Balanced approach for general conversations",
                "weights": {
                    "length_optimal": 3.0,
                    "length_good": 1.0,
                    "complex_reasoning": 2.0,
                    "opinions_ideas": 2.0,
                    "agreement_disagreement": 1.0,
                    "filler_penalty": -0.5,
                    "exact_repetition_penalty": -5.0,
                    "high_overlap_penalty": -3.0,
                },
                "thresholds": {
                    "min_words": 3,
                    "optimal_word_range": (5, 50),
                    "good_word_range": (3, 100),
                    "overlap_threshold": 0.7,
                },
                "indicators": {
                    "complex_reasoning": [
                        "because",
                        "however",
                        "therefore",
                        "although",
                        "meanwhile",
                    ],
                    "opinions_ideas": [
                        "think",
                        "believe",
                        "suggest",
                        "propose",
                        "recommend",
                    ],
                    "agreement_disagreement": [
                        "agree",
                        "disagree",
                        "yes",
                        "no",
                        "correct",
                        "wrong",
                    ],
                    "filler_words": [
                        "um",
                        "uh",
                        "like",
                        "you know",
                        "i mean",
                        "sort of",
                        "kind of",
                    ],
                },
            },
            "academic": {
                "description": "Optimized for academic discussions, research presentations, and debates",
                "weights": {
                    "length_optimal": 4.0,
                    "length_good": 1.5,
                    "complex_reasoning": 4.0,
                    "opinions_ideas": 3.0,
                    "agreement_disagreement": 2.0,
                    "filler_penalty": -1.0,
                    "exact_repetition_penalty": -3.0,
                    "high_overlap_penalty": -2.0,
                    "dialogue_acts": {
                        "question": 4.0,
                        "suggestion": 3.0,
                        "agreement": 2.5,
                        "disagreement": 3.0,
                        "statement": 2.0,
                        "acknowledgement": 0.5,
                        "hesitation": -1.5,
                    },
                    "sentiment_strength": 1.0,
                    "verbal_tic_penalty": -2.5,
                    "optimal_readability": 3.0,
                    "topic_relevance": 2.5,
                    "entity_engagement": 2.0,
                },
                "thresholds": {
                    "min_words": 5,
                    "optimal_word_range": (8, 80),
                    "good_word_range": (5, 150),
                    "overlap_threshold": 0.8,
                },
                "indicators": {
                    "complex_reasoning": [
                        "because",
                        "however",
                        "therefore",
                        "although",
                        "meanwhile",
                        "consequently",
                        "furthermore",
                        "moreover",
                        "nevertheless",
                        "nonetheless",
                        "thus",
                        "hence",
                    ],
                    "opinions_ideas": [
                        "think",
                        "believe",
                        "suggest",
                        "propose",
                        "recommend",
                        "consider",
                        "hypothesize",
                        "conclude",
                        "argue",
                        "demonstrate",
                        "theorize",
                        "postulate",
                    ],
                    "agreement_disagreement": [
                        "agree",
                        "disagree",
                        "yes",
                        "no",
                        "correct",
                        "wrong",
                        "exactly",
                        "absolutely",
                        "precisely",
                        "inaccurate",
                        "valid",
                        "invalid",
                    ],
                    "filler_words": [
                        "um",
                        "uh",
                        "like",
                        "you know",
                        "i mean",
                        "sort of",
                        "kind of",
                        "basically",
                        "actually",
                    ],
                },
            },
            "business": {
                "description": "Optimized for business meetings, negotiations, and professional discussions",
                "weights": {
                    "length_optimal": 3.5,
                    "length_good": 1.0,
                    "complex_reasoning": 2.5,
                    "opinions_ideas": 4.0,
                    "agreement_disagreement": 2.5,
                    "filler_penalty": -0.3,
                    "exact_repetition_penalty": -4.0,
                    "high_overlap_penalty": -2.5,
                    "dialogue_acts": {
                        "question": 3.5,
                        "suggestion": 4.0,
                        "agreement": 3.0,
                        "disagreement": 2.5,
                        "statement": 2.5,
                        "acknowledgement": 1.0,
                        "hesitation": -0.5,
                    },
                    "sentiment_strength": 1.5,
                    "verbal_tic_penalty": -1.5,
                    "optimal_readability": 2.5,
                    "topic_relevance": 3.0,
                    "entity_engagement": 2.5,
                },
                "thresholds": {
                    "min_words": 3,
                    "optimal_word_range": (5, 60),
                    "good_word_range": (3, 120),
                    "overlap_threshold": 0.75,
                },
                "indicators": {
                    "complex_reasoning": [
                        "because",
                        "however",
                        "therefore",
                        "although",
                        "meanwhile",
                        "consequently",
                    ],
                    "opinions_ideas": [
                        "think",
                        "believe",
                        "suggest",
                        "propose",
                        "recommend",
                        "consider",
                        "feel",
                        "assume",
                        "recommend",
                        "advise",
                        "propose",
                        "plan",
                    ],
                    "agreement_disagreement": [
                        "agree",
                        "disagree",
                        "yes",
                        "no",
                        "correct",
                        "wrong",
                        "exactly",
                        "absolutely",
                        "sounds good",
                        "i'm on board",
                        "approved",
                        "rejected",
                    ],
                    "filler_words": [
                        "um",
                        "uh",
                        "like",
                        "you know",
                        "i mean",
                        "sort of",
                        "kind of",
                    ],
                },
            },
            "casual": {
                "description": "Optimized for casual conversations, social discussions, and informal chats",
                "weights": {
                    "length_optimal": 2.5,
                    "length_good": 1.5,
                    "complex_reasoning": 1.5,
                    "opinions_ideas": 2.5,
                    "agreement_disagreement": 2.0,
                    "filler_penalty": -0.2,
                    "exact_repetition_penalty": -3.0,
                    "high_overlap_penalty": -2.0,
                    "dialogue_acts": {
                        "question": 2.5,
                        "suggestion": 2.0,
                        "agreement": 2.5,
                        "disagreement": 2.0,
                        "statement": 2.0,
                        "acknowledgement": 1.5,
                        "hesitation": -0.3,
                    },
                    "sentiment_strength": 2.0,
                    "verbal_tic_penalty": -0.5,
                    "optimal_readability": 1.5,
                    "topic_relevance": 1.0,
                    "entity_engagement": 1.5,
                },
                "thresholds": {
                    "min_words": 2,
                    "optimal_word_range": (3, 40),
                    "good_word_range": (2, 80),
                    "overlap_threshold": 0.6,
                },
                "indicators": {
                    "complex_reasoning": ["because", "but", "so", "though", "anyway"],
                    "opinions_ideas": [
                        "think",
                        "feel",
                        "like",
                        "guess",
                        "suppose",
                        "maybe",
                    ],
                    "agreement_disagreement": [
                        "yeah",
                        "no",
                        "right",
                        "wrong",
                        "sure",
                        "okay",
                        "cool",
                    ],
                    "filler_words": [
                        "um",
                        "uh",
                        "like",
                        "you know",
                        "i mean",
                        "sort of",
                        "kind of",
                        "basically",
                        "actually",
                        "literally",
                    ],
                },
            },
            "technical": {
                "description": "Optimized for technical discussions, code reviews, and troubleshooting sessions",
                "weights": {
                    "length_optimal": 3.0,
                    "length_good": 1.0,
                    "complex_reasoning": 3.5,
                    "opinions_ideas": 2.0,
                    "agreement_disagreement": 3.0,
                    "filler_penalty": -0.8,
                    "exact_repetition_penalty": -2.0,
                    "high_overlap_penalty": -1.5,
                    "dialogue_acts": {
                        "question": 4.0,
                        "suggestion": 3.5,
                        "agreement": 2.5,
                        "disagreement": 3.5,
                        "statement": 2.5,
                        "acknowledgement": 1.0,
                        "hesitation": -1.0,
                    },
                    "sentiment_strength": 1.0,
                    "verbal_tic_penalty": -2.0,
                    "optimal_readability": 2.0,
                    "topic_relevance": 4.0,
                    "entity_engagement": 3.0,
                },
                "thresholds": {
                    "min_words": 4,
                    "optimal_word_range": (6, 70),
                    "good_word_range": (4, 130),
                    "overlap_threshold": 0.85,
                },
                "indicators": {
                    "complex_reasoning": [
                        "because",
                        "however",
                        "therefore",
                        "although",
                        "meanwhile",
                        "consequently",
                        "furthermore",
                        "moreover",
                        "nevertheless",
                    ],
                    "opinions_ideas": [
                        "think",
                        "believe",
                        "suggest",
                        "propose",
                        "recommend",
                        "consider",
                        "argue",
                        "demonstrate",
                        "prove",
                    ],
                    "agreement_disagreement": [
                        "agree",
                        "disagree",
                        "yes",
                        "no",
                        "correct",
                        "wrong",
                        "exactly",
                        "absolutely",
                        "precisely",
                        "inaccurate",
                        "false",
                    ],
                    "filler_words": [
                        "um",
                        "uh",
                        "like",
                        "you know",
                        "i mean",
                        "sort of",
                        "kind of",
                    ],
                },
            },
            "interview": {
                "description": "Optimized for job interviews, Q&A sessions, and structured conversations",
                "weights": {
                    "length_optimal": 3.5,
                    "length_good": 1.0,
                    "complex_reasoning": 2.0,
                    "opinions_ideas": 3.5,
                    "agreement_disagreement": 1.5,
                    "filler_penalty": -0.5,
                    "exact_repetition_penalty": -3.5,
                    "high_overlap_penalty": -2.5,
                    "dialogue_acts": {
                        "question": 4.5,
                        "suggestion": 2.0,
                        "agreement": 1.5,
                        "disagreement": 2.0,
                        "statement": 3.0,
                        "acknowledgement": 1.0,
                        "hesitation": -1.0,
                    },
                    "sentiment_strength": 1.5,
                    "verbal_tic_penalty": -1.5,
                    "optimal_readability": 2.5,
                    "topic_relevance": 3.5,
                    "entity_engagement": 2.0,
                },
                "thresholds": {
                    "min_words": 4,
                    "optimal_word_range": (6, 60),
                    "good_word_range": (4, 100),
                    "overlap_threshold": 0.75,
                },
                "indicators": {
                    "complex_reasoning": [
                        "because",
                        "however",
                        "therefore",
                        "although",
                        "meanwhile",
                    ],
                    "opinions_ideas": [
                        "think",
                        "believe",
                        "suggest",
                        "propose",
                        "recommend",
                        "consider",
                        "feel",
                        "experience",
                        "worked",
                        "developed",
                    ],
                    "agreement_disagreement": [
                        "agree",
                        "disagree",
                        "yes",
                        "no",
                        "correct",
                        "wrong",
                        "exactly",
                        "absolutely",
                    ],
                    "filler_words": [
                        "um",
                        "uh",
                        "like",
                        "you know",
                        "i mean",
                        "sort of",
                        "kind of",
                    ],
                },
            },
        }
    )

    # Individual override options (these override profile settings)
    quality_weights_override: dict[str, float] | None = None
    quality_thresholds_override: dict[str, Any] | None = None
    quality_indicators_override: dict[str, list[str]] | None = None

    max_semantic_comparisons: int = 50000  # Maximum similarity comparisons to perform
    semantic_timeout_seconds: int = 300  # Timeout for semantic analysis (5 minutes)
    semantic_batch_size: int = (
        64  # Batch size for processing (increased from 32 for better performance)
    )

    # General
    output_formats: list[str] = field(default_factory=lambda: ["json", "csv", "png"])
    use_dag_pipeline: bool = True  # Use DAG pipeline for better dependency management

    # Quick vs Full Analysis Mode
    analysis_mode: str = "quick"  # "quick" or "full"
    quick_analysis_settings: dict[str, Any] = field(
        default_factory=lambda: {
            "use_lightweight_models": True,
            "semantic_method": "simple",
            "max_segments_for_semantic": 800,
            "max_semantic_comparisons": 15000,
            "ner_use_light_model": False,
            "ner_max_segments": 2000,
            "skip_advanced_semantic": True,
            "skip_geocoding": False,
            "reduced_chart_generation": True,
            "semantic_profile": "balanced",
        }
    )
    full_analysis_settings: dict[str, Any] = field(
        default_factory=lambda: {
            "use_lightweight_models": False,
            "semantic_method": "advanced",
            "max_segments_for_semantic": 1000,
            "max_semantic_comparisons": 30000,  # Reduced from 50000 for faster processing
            "max_segments_per_speaker": 400,  # Increased from 200 for full mode
            "max_segments_for_cross_speaker": 1000,  # Increased from 500 for full mode
            "ner_use_light_model": False,
            "ner_max_segments": 5000,
            "skip_advanced_semantic": False,
            "skip_geocoding": False,
            "reduced_chart_generation": False,
            "semantic_profile": "balanced",
        }
    )

    # Module-specific configurations
    topic_modeling: TopicModelingConfig = field(
        default_factory=lambda: TopicModelingConfig()
    )
    acts: ActsConfig = field(default_factory=lambda: ActsConfig())
    tag_extraction: TagExtractionConfig = field(
        default_factory=lambda: TagExtractionConfig()
    )
    qa_analysis: QAAnalysisConfig = field(default_factory=lambda: QAAnalysisConfig())
    temporal_dynamics: TemporalDynamicsConfig = field(
        default_factory=lambda: TemporalDynamicsConfig()
    )
    pauses: PausesConfig = field(default_factory=lambda: PausesConfig())
    echoes: EchoesConfig = field(default_factory=lambda: EchoesConfig())
    momentum: MomentumConfig = field(default_factory=lambda: MomentumConfig())
    moments: MomentsConfig = field(default_factory=lambda: MomentsConfig())
    convokit: ConvokitConfig = field(default_factory=lambda: ConvokitConfig())
    vectorization: VectorizationConfig = field(
        default_factory=lambda: VectorizationConfig()
    )
    voice: VoiceConfig = field(default_factory=lambda: VoiceConfig())
    affect_tension: AffectTensionConfig = field(
        default_factory=lambda: AffectTensionConfig()
    )

    # Profile management - active profiles for each module
    active_topic_modeling_profile: str = "default"
    active_acts_profile: str = "default"
    active_tag_extraction_profile: str = "default"
    active_qa_analysis_profile: str = "default"
    active_temporal_dynamics_profile: str = "default"
    active_vectorization_profile: str = "default"


@dataclass
class TopicModelingConfig:
    """Configuration for topic modeling analysis."""

    # Vectorizer settings
    max_features: int = 1000
    min_df: int = 2
    max_df: float = 0.95
    ngram_range: tuple[int, int] = (1, 2)

    # Model settings
    random_state: int = 42
    max_iter_lda: int = 50
    max_iter_nmf: int = 10000
    alpha_H: float = 0.1  # NMF regularization
    tol: float = 1e-2  # NMF tolerance
    learning_method: str = "batch"  # LDA learning method

    # Search settings
    k_range: tuple[int, int] = (3, 15)  # Topic count search range
    test_size: float = 0.2  # Train/test split


@dataclass
class ActsConfig:
    """Configuration for dialogue acts classification."""

    # Classification method
    method: str = "both"  # "rules", "ml", or "both"

    # Context settings
    use_context: bool = True
    context_window_size: int = 3
    context_window_type: str = "sliding"  # "fixed", "dynamic", or "sliding"
    include_speaker_info: bool = True
    include_timing_info: bool = False

    # Confidence thresholds
    min_confidence: float = 0.7
    high_confidence_threshold: float = 0.9
    ensemble_weight_transformer: float = 0.5
    ensemble_weight_ml: float = 0.3
    ensemble_weight_rules: float = 0.2

    # Machine learning settings
    ml_model_name: str = "bert-base-uncased"
    ml_use_gpu: bool = False
    ml_batch_size: int = 32
    ml_max_length: int = 512

    # Rule-based settings
    rules_use_enhanced_patterns: bool = True
    rules_use_fallback_logic: bool = True
    rules_confidence_boost_exact_match: float = 0.1
    rules_context_boost_factor: float = 0.15

    # Performance settings
    enable_caching: bool = True
    cache_size: int = 1000


@dataclass
class TagExtractionConfig:
    """Configuration for tag extraction analysis."""

    early_window_seconds: int = 60
    early_segments: int = 10
    min_confidence: float = 0.6


@dataclass
class QAAnalysisConfig:
    """Configuration for Q&A analysis."""

    response_time_threshold: float = 10.0  # seconds

    # Scoring weights
    weight_directness: float = 0.3
    weight_completeness: float = 0.3
    weight_relevance: float = 0.25
    weight_length: float = 0.15

    # Matching thresholds
    min_match_threshold: float = 0.3
    good_match_threshold: float = 0.5
    high_match_threshold: float = 0.7

    # Answer length thresholds
    min_answer_length: int = 2
    optimal_answer_length: int = 5
    max_answer_length: int = 50


@dataclass
class ConvokitConfig:
    """Configuration for ConvoKit coordination analysis."""

    exclude_unidentified: bool = True
    min_tokens_per_utterance: int = 1
    max_utterances: Optional[int] = None
    reply_linking_strategy: str = "prev_diff_speaker"
    response_threshold: float = 2.0
    enable_politeness: bool = False


@dataclass
class TemporalDynamicsConfig:
    """Configuration for temporal dynamics analysis."""

    window_size: float = 30.0  # seconds

    # Engagement score weights
    weight_segment_factor: float = 0.4
    weight_length_factor: float = 0.3
    weight_question_factor: float = 0.3

    # Normalization factors
    max_segments_normalization: float = 10.0
    max_questions_normalization: float = 5.0

    # Phase detection thresholds
    opening_phase_percentage: float = 0.1  # First 10% or 2 minutes
    opening_phase_max_seconds: float = 120.0  # 2 minutes
    closing_phase_percentage: float = 0.1  # Last 10% or 2 minutes
    closing_phase_max_seconds: float = 120.0  # 2 minutes

    # Trend detection thresholds
    sentiment_change_threshold: float = 0.1
    engagement_change_threshold: float = 0.05
    speaking_rate_change_threshold: float = 10.0  # words per minute


@dataclass
class AffectTensionConfig:
    """Configuration for affect_tension (emotion + sentiment mismatch) analysis."""

    # Thresholds for mismatch and trust
    mismatch_compound_threshold: float = -0.1  # sentiment compound below = negative
    trust_like_threshold: float = 0.3  # emotion trust-like score above = high trust
    pos_emotion_threshold: float = 0.3  # emotion score above = positive emotion

    # Weights for derived indices
    weight_posneg_mismatch: float = 0.4
    weight_trust_neutral: float = 0.3
    weight_entropy: float = 0.15
    weight_volatility: float = 0.15

    # Rolling window: by segment count or by seconds (use one)
    window_segments: int = 5  # rolling window in segments
    window_seconds: Optional[float] = None  # if set, overrides window_segments by time


@dataclass
class PausesConfig:
    """Configuration for pauses analysis."""

    min_long_pause_seconds: float = 2.0
    post_question_multiplier: float = 1.5
    percentile_long_pause: float = 0.95


@dataclass
class EchoesConfig:
    """Configuration for echoes analysis."""

    lookback_seconds: float = 240.0
    max_candidates: int = 50
    explicit_quote_weight: float = 1.0
    lexical_echo_threshold: float = 0.6
    paraphrase_threshold: float = 0.75
    min_tokens: int = 5
    exclude_phrases: list[str] = field(
        default_factory=lambda: ["yeah", "exactly", "right"]
    )
    enable_semantic_paraphrase: bool = False
    echo_burst_window_seconds: float = 25.0
    echo_burst_min_events: int = 3
    echo_burst_percentile_threshold: float = 0.95


@dataclass
class MomentumConfig:
    """Configuration for momentum analysis."""

    window_length_seconds: float = 60.0
    window_step_seconds: float = 30.0
    stall_threshold_percentile: float = 0.15
    min_stall_duration_seconds: float = 30.0
    momentum_cliff_threshold: float = -0.2
    novelty_lookback_windows: int = 3
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "pause_rate": -0.3,
            "repetition_rate": -0.3,
            "loop_rate": -0.2,
            "novelty": 0.4,
            "turn_energy": 0.3,
        }
    )


@dataclass
class MomentsConfig:
    """Configuration for moments analysis."""

    top_n: int = 20
    merge_seconds: float = 20.0
    weight_map: dict[str, float] = field(
        default_factory=lambda: {
            "long_pause": 0.3,
            "post_question_silence": 0.5,
            "momentum_cliff": 0.4,
            "echo_burst": 0.3,
            "emotion_switch": 0.4,
            "unanswered_question": 0.5,
        }
    )
    diversity_bonus: float = 0.2
    multi_speaker_bonus: float = 0.15
    write_markdown: bool = False


@dataclass
class VectorizationConfig:
    """Shared configuration for vectorization across modules."""

    max_features: int = 1000
    min_df: int = 1
    max_df: float = 0.95
    ngram_range: tuple[int, int] = (1, 2)

    # Word clouds specific
    wordcloud_max_features: int = 300
    wordcloud_ngram_range: tuple[int, int] = (1, 2)


@dataclass
class VoiceConfig:
    """Configuration for voice modality analysis (CPU-first)."""

    enabled: bool = True

    # Feature extraction
    sample_rate: int = 16000
    vad_mode: int = 2
    pad_s: float = 0.15
    max_seconds_for_pitch: float = 20.0
    max_segments_considered: int | None = None

    # openSMILE eGeMAPS extraction
    egemaps_enabled: bool = True

    # Optional deep mode (lazy imports; best-effort)
    # When enabled, TranscriptX will try to infer segment-level vocal emotion and
    # a coarse valence proxy using an audio emotion recognition model (CPU ok, slow).
    # If dependencies/models are unavailable, it falls back to classic proxies.
    deep_mode: bool = False
    deep_model_name: str = "superb/wav2vec2-base-superb-er"
    deep_max_seconds: float = 12.0

    # Cache / storage
    store_parquet: str = "auto"  # auto|on|off
    strict_audio_hash: bool = False

    # Aggregations
    mismatch_threshold: float = 0.6
    top_k_moments: int = 30
    drift_threshold: float = 2.5

    bin_seconds: float = 30.0
    smoothing_alpha: float = 0.25

    # Speaker filtering behavior for global curves
    include_unnamed_in_global_curves: bool = True
