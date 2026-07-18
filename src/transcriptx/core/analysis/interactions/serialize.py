"""Shared serialization for interactions analysis results (current + legacy paths)."""

from __future__ import annotations

from typing import Any, Mapping

from transcriptx.core.analysis.interactions.roles import INTERACTIONS_SEMANTICS_VERSION


def serialize_equity(equity: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a JSON-safe copy of the canonical equity object."""
    if not equity:
        from transcriptx.core.analysis.interactions.equity import empty_equity

        return empty_equity()
    return {
        "floor_share": dict(equity.get("floor_share") or {}),
        "floor_entropy": equity.get("floor_entropy"),
        "floor_equity_index": equity.get("floor_equity_index"),
        "interruption_asymmetry": dict(equity.get("interruption_asymmetry") or {}),
        "interruption_asymmetry_index": equity.get("interruption_asymmetry_index"),
        "response_latency": {
            speaker: dict(stats)
            for speaker, stats in (equity.get("response_latency") or {}).items()
        },
        "response_latency_fairness_index": equity.get(
            "response_latency_fairness_index"
        ),
        "abstentions": [
            {"metric": a.get("metric"), "reason": a.get("reason")}
            for a in (equity.get("abstentions") or [])
            if isinstance(a, Mapping)
        ],
    }


def serialize_interactions_summary(
    analysis_results: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Shared summary payload for OutputService and legacy create_summary_json paths.

    Includes semantics_version and the canonical equity object.
    """
    equity = serialize_equity(analysis_results.get("equity"))
    speakers = sorted(analysis_results.get("total_interactions", {}).keys())
    speaker_stats = {
        speaker: {
            "interruptions_initiated": analysis_results.get(
                "interruption_initiated", {}
            ).get(speaker, 0),
            "interruptions_received": analysis_results.get(
                "interruption_received", {}
            ).get(speaker, 0),
            "responses_initiated": analysis_results.get(
                "responses_initiated", {}
            ).get(speaker, 0),
            "responses_received": analysis_results.get("responses_received", {}).get(
                speaker, 0
            ),
            "net_interruption_balance": analysis_results.get(
                "net_interruption_balance", {}
            ).get(speaker, 0),
            "net_response_balance": analysis_results.get(
                "net_response_balance", {}
            ).get(speaker, 0),
            "dominance_score": analysis_results.get("dominance_scores", {}).get(
                speaker, 0
            ),
        }
        for speaker in speakers
    }
    global_stats = {
        "semantics_version": analysis_results.get(
            "semantics_version", INTERACTIONS_SEMANTICS_VERSION
        ),
        "total_interactions": analysis_results.get("total_interactions_count", 0),
        "unique_speakers": analysis_results.get("unique_speakers", 0),
        "equity": equity,
    }
    return {
        "semantics_version": global_stats["semantics_version"],
        "global": global_stats,
        "speakers": speaker_stats,
        "equity": equity,
    }
