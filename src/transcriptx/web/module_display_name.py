"""Short human-readable module titles for Charts gallery rows and search."""

from __future__ import annotations

# Prefer concise gallery/report-style titles over long ModuleInfo.description strings.
_GALLERY_MODULE_DISPLAY_NAMES: dict[str, str] = {
    "affect_tension": "Affect tension",
    "entity_sentiment": "Entity sentiment",
    "qa_analysis": "Q&A analysis",
    "semantic_similarity_advanced": "Semantic similarity",
    "semantic_similarity_v2": "Semantic similarity v2",
    "voice": "Voice / prosody",
    "voice_charts_core": "Voice charts",
    "voice_features": "Voice features",
    "voice_mismatch": "Voice mismatch",
    "voice_tension": "Voice tension",
    "voice_fingerprint": "Voice fingerprint",
    "voice_contours": "Voice contours",
    "prosody_dashboard": "Prosody dashboard",
    "wordclouds": "Word clouds",
    "ner": "Named entities",
    "acts": "Dialogue acts",
    "llm_summary": "LLM summary",
    "llm_speaker_summary": "LLM speaker summary",
    "llm_action_items": "LLM action items",
    "llm_custom_qa": "LLM custom Q&A",
    "chart_descriptions": "Chart descriptions",
    "topic_shift": "Topic shift",
    "topic_modeling": "Topic modeling",
    "fine_grained_emotion": "Fine-grained emotion",
    "contextual_emotion": "Contextual emotion",
    "conversation_loops": "Conversation loops",
    "transcript_output": "Transcript output",
    "simplified_transcript": "Simplified transcript",
    "transcript_quality": "Transcript quality",
    "temporal_dynamics": "Temporal dynamics",
    "insight_eligibility": "Insight eligibility",
    "lexical_diversity": "Lexical diversity",
    "epistemic_markers": "Epistemic markers",
    "politeness": "Politeness markers",
    "narrative_summary": "Narrative summary",
}


def gallery_module_display_name(module_id: str | None) -> str:
    """Short gallery label for a module registry id (or ``Other``)."""
    if not module_id:
        return "Other"
    override = _GALLERY_MODULE_DISPLAY_NAMES.get(module_id)
    if override:
        return override
    return module_id.replace("_", " ").strip().title() or "Other"
