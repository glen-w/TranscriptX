"""Compatibility entry point for module registry specs.

Domain-specific definition builders live in module_specs/.
Snapshot tests in tests/core/pipeline/test_module_registry_specs_snapshot.py
must pass with no metadata diff unless an intentional registry change is made.
"""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Requirement

EXTRA_REPRESENTATIVE: Dict[str, str] = {
    "voice": "opensmile",
    "emotion": "transformers",
    "nlp": "spacy",
    "ner": "spacy",
    "bertopic": "bertopic",
    "maps": "folium",
    "visualization": "matplotlib",
    "plotly": "plotly",
}

MODULE_CLASS_MAP: Dict[str, tuple[str, str]] = {
    "corrections": ("transcriptx.core.analysis.corrections", "CorrectionsAnalysis"),
    "emotion": ("transcriptx.core.analysis.emotion", "EmotionAnalysis"),
    "contagion": ("transcriptx.core.analysis.contagion", "ContagionAnalysis"),
    "sentiment": ("transcriptx.core.analysis.sentiment", "SentimentAnalysis"),
    "acts": ("transcriptx.core.analysis.acts.analysis", "ActsAnalysis"),
    "stats": ("transcriptx.core.analysis.stats", "StatsAnalysis"),
    "interactions": (
        "transcriptx.core.analysis.interactions.analysis",
        "InteractionsAnalysis",
    ),
    "ner": ("transcriptx.core.analysis.ner", "NERAnalysis"),
    "entity_sentiment": (
        "transcriptx.core.analysis.entity_sentiment",
        "EntitySentimentAnalysis",
    ),
    "affect_tension": (
        "transcriptx.core.analysis.affect_tension",
        "AffectTensionAnalysis",
    ),
    "conversation_loops": (
        "transcriptx.core.analysis.conversation_loops.analysis",
        "ConversationLoopsAnalysis",
    ),
    "topic_modeling": (
        "transcriptx.core.analysis.topic_modeling",
        "TopicModelingAnalysis",
    ),
    "semantic_similarity": (
        "transcriptx.core.analysis.semantic_similarity",
        "SemanticSimilarityAnalysis",
    ),
    "semantic_similarity_advanced": (
        "transcriptx.core.analysis.semantic_similarity",
        "SemanticSimilarityAdvancedAnalysis",
    ),
    "semantic_similarity_v2": (
        "transcriptx.core.analysis.semantic_similarity_v2",
        "SemanticSimilarityV2Analysis",
    ),
    "transcript_output": (
        "transcriptx.core.analysis.transcript_output",
        "TranscriptOutputAnalysis",
    ),
    "simplified_transcript": (
        "transcriptx.core.analysis.simplified_transcript",
        "SimplifiedTranscriptAnalysis",
    ),
    "wordclouds": (
        "transcriptx.core.analysis.wordclouds.analysis",
        "WordcloudsAnalysis",
    ),
    "tics": ("transcriptx.core.analysis.tics", "TicsAnalysis"),
    "insight_eligibility": (
        "transcriptx.core.analysis.insight_eligibility",
        "InsightEligibilityAnalysis",
    ),
    "understandability": (
        "transcriptx.core.analysis.understandability",
        "UnderstandabilityAnalysis",
    ),
    "lexical_diversity": (
        "transcriptx.core.analysis.lexical_diversity",
        "LexicalDiversityAnalysis",
    ),
    "temporal_dynamics": (
        "transcriptx.core.analysis.temporal_dynamics.analysis",
        "TemporalDynamicsAnalysis",
    ),
    "qa_analysis": ("transcriptx.core.analysis.qa_analysis.analysis", "QAAnalysis"),
    "pauses": ("transcriptx.core.analysis.dynamics.pauses", "PausesAnalysis"),
    "echoes": ("transcriptx.core.analysis.dynamics.echoes", "EchoesAnalysis"),
    "momentum": ("transcriptx.core.analysis.dynamics.momentum", "MomentumAnalysis"),
    "moments": ("transcriptx.core.analysis.dynamics.moments", "MomentsAnalysis"),
    "highlights": ("transcriptx.core.analysis.highlights", "HighlightsAnalysis"),
    "summary": ("transcriptx.core.analysis.summary", "SummaryAnalysis"),
    "narrative_summary": (
        "transcriptx.core.analysis.narrative_summary",
        "NarrativeSummaryAnalysis",
    ),
    "llm_summary": (
        "transcriptx.core.analysis.llm_summary",
        "LLMSummaryAnalysis",
    ),
    "llm_speaker_summary": (
        "transcriptx.core.analysis.llm_speaker_summary",
        "LLMSpeakerSummaryAnalysis",
    ),
    "llm_action_items": (
        "transcriptx.core.analysis.llm_action_items",
        "LLMActionItemsAnalysis",
    ),
    "insights": ("transcriptx.core.analysis.insights", "InsightsAnalysis"),
    "voice_features": (
        "transcriptx.core.analysis.voice_features",
        "VoiceFeaturesAnalysis",
    ),
    "voice_mismatch": (
        "transcriptx.core.analysis.voice_mismatch",
        "VoiceMismatchAnalysis",
    ),
    "voice_tension": (
        "transcriptx.core.analysis.voice_tension",
        "VoiceTensionAnalysis",
    ),
    "voice_fingerprint": (
        "transcriptx.core.analysis.voice_fingerprint",
        "VoiceFingerprintAnalysis",
    ),
    "prosody_dashboard": (
        "transcriptx.core.analysis.voice.dashboard",
        "ProsodyDashboardAnalysis",
    ),
    "voice_charts_core": (
        "transcriptx.core.analysis.voice.charts_core",
        "VoiceChartsCoreAnalysis",
    ),
    "voice_contours": (
        "transcriptx.core.analysis.voice.contours",
        "VoiceContoursAnalysis",
    ),
}


def build_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    """Return declarative module metadata definitions."""
    from transcriptx.core.pipeline.module_specs import build_all_module_definitions

    return build_all_module_definitions(default_requirements)
