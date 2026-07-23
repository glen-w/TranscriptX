"""Summary extractor for epistemic markers."""

from typing import Any, Dict

from . import register_extractor


def extract_epistemic_markers_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    global_stats = data.get("epistemic_markers_global_stats") or data.get(
        "global_stats", {}
    )
    if not isinstance(global_stats, dict):
        return
    if data.get("usable") is False:
        summary.setdefault("highlights", []).append(
            "Epistemic markers abstained (unsupported language or empty usable result)."
        )
        return
    hits = global_stats.get("total_marker_hits")
    rate = global_stats.get("hits_per_100_tokens")
    if hits is not None:
        summary["key_metrics"]["Epistemic marker hits"] = str(int(hits))
    if rate is not None:
        summary["key_metrics"]["Epistemic hits / 100 tokens"] = f"{float(rate):.2f}"
    hedge = global_stats.get("hedge_share")
    boost = global_stats.get("booster_share")
    if hedge is not None:
        summary["key_metrics"]["Hedge share"] = f"{float(hedge):.3f}"
    if boost is not None:
        summary["key_metrics"]["Booster share"] = f"{float(boost):.3f}"
    summary.setdefault("highlights", []).append(
        "Epistemic markers are lexicon densities — distinct from dialogue-act uncertainty and filler tics."
    )


register_extractor("epistemic_markers", extract_epistemic_markers_summary)
