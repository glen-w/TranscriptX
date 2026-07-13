"""Summary extractor for lexical diversity analysis."""

from typing import Any, Dict

from . import register_extractor


def extract_lexical_diversity_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    """Extract summary from lexical diversity analysis data."""
    global_stats = data.get("lexical_diversity_global_stats") or data.get(
        "global_stats", {}
    )
    if not isinstance(global_stats, dict):
        return
    ttr = global_stats.get("ttr")
    mtld = global_stats.get("mtld")
    hapax_rate = global_stats.get("hapax_rate")
    if ttr is not None:
        summary["key_metrics"]["Global TTR"] = f"{float(ttr):.3f}"
    if mtld is not None:
        summary["key_metrics"]["Global MTLD"] = f"{float(mtld):.1f}"
    elif global_stats.get("token_count", 0):
        summary["key_metrics"]["Global MTLD"] = "n/a (short input)"
    if hapax_rate is not None:
        summary["key_metrics"]["Global hapax rate"] = f"{float(hapax_rate):.3f}"
    summary.setdefault("highlights", []).append(
        "Lexical diversity metrics are length-sensitive; interpret TTR and hapax rate in context."
    )


register_extractor("lexical_diversity", extract_lexical_diversity_summary)
