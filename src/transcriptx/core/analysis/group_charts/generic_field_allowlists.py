"""
Per-agg allowlists for GenericNumericGroupChartGenerator session fields.

If an ``agg_id`` is absent from this map, the generic generator charts all numeric
session columns (subject to ``max_charts``). Listed ids only chart approved keys so
Phase-4 curation applies at field level, not only registry membership.

Source of truth for outcomes: ``docs/archive/assessments/group_charts_phase4_outcome_table.md``.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Optional

# agg_id -> allowed session row metric keys (after one-level dict flattening, e.g. counts_by_kind.echo)
GENERIC_SESSION_FIELD_ALLOWLISTS: Dict[str, FrozenSet[str]] = {
    "conversation_loops": frozenset({"total_loops", "unique_speaker_pairs"}),
    "interactions": frozenset(
        {
            "total_interactions",
            "unique_speakers",
            "floor_equity_index",
            "interruption_asymmetry_index",
            "response_latency_fairness_index",
        }
    ),
    "qa_analysis": frozenset(
        {
            "total_questions",
            "answered",
            "unanswered",
            "answer_rate",
            "avg_response_time",
            "avg_quality_score",
        }
    ),
    "echoes": frozenset(
        {
            "total_events",
            "counts_by_kind.echo",
            "counts_by_kind.paraphrase",
            "counts_by_kind.explicit_quote",
        }
    ),
    "momentum": frozenset(
        {
            "window_length_seconds",
            "window_step_seconds",
            "stall_threshold",
            "stall_zone_count",
            "momentum_cliff_count",
        }
    ),
    "affect_tension": frozenset(
        {
            "polite_tension_index",
            "suppressed_conflict_score",
            "institutional_tone_affect_delta",
        }
    ),
    "understandability": frozenset(
        {
            "flesch_reading_ease",
            "gunning_fog_index",
            "smog_index",
            "automated_readability_index",
            "avg_sentence_length",
            "lexical_density",
            "word_count",
            "sentence_count",
        }
    ),
    "lexical_diversity": frozenset(
        {
            "ttr",
            "mtld",
            "hapax_rate",
            "token_count",
        }
    ),
    "simplified_transcript": frozenset(
        {
            "total_original",
            "total_simplified",
            "removed_count",
        }
    ),
    "tics": frozenset({"total_tics"}),
    "epistemic_markers": frozenset(
        {
            "total_marker_hits",
            "token_count",
            "hits_per_100_tokens",
            "hedge_share",
            "booster_share",
        }
    ),
    "politeness": frozenset(
        {
            "total_marker_hits",
            "token_count",
            "hits_per_100_tokens",
            "soft_request_ratio",
        }
    ),
    "llm_action_items": frozenset({"item_count"}),
    "insights": frozenset(
        {"theme_count", "recurring_idea_count", "notable_moment_count"}
    ),
    "semantic_similarity": frozenset(
        {
            "total_repetitions",
            "unique_patterns",
            "motif_count",
            "recurring_motif_count",
            "drift_score",
        }
    ),
    "voice_mismatch": frozenset(
        {"moments_count", "mismatch_score_mean", "mismatch_score_max"}
    ),
    "voice_tension": frozenset({"bins", "tension_mean", "tension_max"}),
    "voice_fingerprint": frozenset({"speakers", "drift_moment_count"}),
}


def allowed_numeric_keys_for_generic_agg(agg_id: str) -> Optional[FrozenSet[str]]:
    """Return allowlist for ``agg_id``, or ``None`` when all numeric fields remain eligible."""
    return GENERIC_SESSION_FIELD_ALLOWLISTS.get(agg_id)
