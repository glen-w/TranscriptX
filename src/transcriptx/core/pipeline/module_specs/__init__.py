"""Compose domain module definition builders into a single registry."""

from __future__ import annotations

from typing import Dict, List

from transcriptx.core.domain.module_requirements import Requirement

from .conversation import build_conversation_module_definitions
from .core import build_core_module_definitions
from .exports import build_exports_module_definitions
from .nlp import build_nlp_module_definitions
from .qa import build_qa_module_definitions
from .speakers import build_speakers_module_definitions
from .summary import build_summary_module_definitions
from .topics import build_topics_module_definitions

# Registry insertion order only — NOT UI display order.
# UI grouping/order remains owned by web/module_ui_groups.py.
MODULE_REGISTRY_ORDER: tuple[str, ...] = (
    "acts",
    "conversation_loops",
    "contagion",
    "emotion",
    "contextual_emotion",
    "fine_grained_emotion",
    "entity_sentiment",
    "affect_tension",
    "interactions",
    "ner",
    "semantic_similarity",
    "sentiment",
    "epistemic_markers",
    "keyphrases",
    "stats",
    "topic_modeling",
    "bertopic",
    "transcript_output",
    "simplified_transcript",
    "understandability",
    "lexical_diversity",
    "wordclouds",
    "tics",
    "transcript_quality",
    "insight_eligibility",
    "temporal_dynamics",
    "qa_analysis",
    "pauses",
    "echoes",
    "politeness",
    "tag_extraction",
    "momentum",
    "topic_shift",
    "moments",
    "highlights",
    "summary",
    "narrative_summary",
    "llm_summary",
    "llm_speaker_summary",
    "llm_action_items",
    "llm_custom_qa",
    "chart_descriptions",
    "insights",
    "voice_features",
    "voice_mismatch",
    "voice_tension",
    "voice_fingerprint",
    "prosody_dashboard",
    "voice_charts_core",
    "voice_contours",
)


def _merge_domain_fragments(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    by_id: Dict[str, Dict] = {}
    for builder in (
        build_core_module_definitions,
        build_conversation_module_definitions,
        build_nlp_module_definitions,
        build_topics_module_definitions,
        build_exports_module_definitions,
        build_qa_module_definitions,
        build_summary_module_definitions,
        build_speakers_module_definitions,
    ):
        fragment = builder(default_requirements)
        overlap = set(by_id) & set(fragment)
        if overlap:
            raise ValueError(
                "module registry duplicate ids across domain builders: "
                f"{sorted(overlap)}"
            )
        by_id.update(fragment)

    order_set = set(MODULE_REGISTRY_ORDER)
    fragment_ids = set(by_id)
    missing = order_set - fragment_ids
    extra = fragment_ids - order_set
    if missing or extra:
        raise ValueError(
            "module registry composition mismatch: "
            f"missing={sorted(missing)} extra={sorted(extra)}"
        )
    return by_id


def build_all_module_definitions(
    default_requirements: List[Requirement],
) -> Dict[str, Dict]:
    by_id = _merge_domain_fragments(default_requirements)
    return {mid: by_id[mid] for mid in MODULE_REGISTRY_ORDER}
