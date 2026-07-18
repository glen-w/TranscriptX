"""
Summary extractor for interactions analysis.
"""

from typing import Any, Dict

from . import register_extractor


def extract_interactions_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from interactions analysis data."""
    interactions = data.get("interactions", [])
    if interactions:
        summary["key_metrics"]["Total Interactions"] = len(interactions)
        pairs = set()
        for item in interactions:
            a = item.get("speaker_a") or item.get("speaker1")
            b = item.get("speaker_b") or item.get("speaker2")
            if a and b:
                # Directed actor→target pair count uses unordered unique pairs for
                # the legacy "Unique Speaker Pairs" metric.
                pairs.add(tuple(sorted([a, b])))
        summary["key_metrics"]["Unique Speaker Pairs"] = len(pairs)

    equity = data.get("equity")
    if not isinstance(equity, dict):
        return

    def _fmt(value: Any) -> str:
        if value is None:
            return "unavailable"
        return f"{float(value):.3f}"

    abstention_by_metric = {
        a.get("metric"): a.get("reason")
        for a in (equity.get("abstentions") or [])
        if isinstance(a, dict) and a.get("metric")
    }

    floor = equity.get("floor_equity_index")
    if floor is None:
        reason = abstention_by_metric.get("floor_equity_index", "abstained")
        summary["key_metrics"]["Floor Equity"] = f"unavailable ({reason})"
    else:
        summary["key_metrics"]["Floor Equity"] = _fmt(floor)

    asym = equity.get("interruption_asymmetry_index")
    if asym is None:
        reason = abstention_by_metric.get("interruption_asymmetry_index", "abstained")
        summary["key_metrics"]["Interruption Inequity"] = f"unavailable ({reason})"
    else:
        summary["key_metrics"]["Interruption Inequity"] = _fmt(asym)
        # Presentation-only balance (not persisted)
        summary["key_metrics"]["Interruption Balance"] = _fmt(1.0 - float(asym))

    latency = equity.get("response_latency_fairness_index")
    if latency is None:
        reason = abstention_by_metric.get(
            "response_latency_fairness_index", "abstained"
        )
        summary["key_metrics"]["Response Latency Fairness"] = f"unavailable ({reason})"
    else:
        summary["key_metrics"]["Response Latency Fairness"] = _fmt(latency)

    summary["notes"] = summary.get("notes") or []
    if isinstance(summary["notes"], list):
        caveat = (
            "Turn-taking equity depends on diarisation quality, timestamp accuracy, "
            "and interaction detector thresholds; treat scores as approximate."
        )
        if caveat not in summary["notes"]:
            summary["notes"].append(caveat)


register_extractor("interactions", extract_interactions_summary)
