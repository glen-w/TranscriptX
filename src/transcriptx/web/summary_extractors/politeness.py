"""Summary extractor for politeness markers."""

from typing import Any, Dict

from . import register_extractor


def extract_politeness_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    global_stats = data.get("politeness_global_stats") or data.get("global_stats", {})
    if not isinstance(global_stats, dict):
        return
    if data.get("usable") is False:
        summary.setdefault("highlights", []).append(
            "Politeness markers abstained (unsupported language or empty usable result)."
        )
        return
    hits = global_stats.get("total_marker_hits")
    rate = global_stats.get("hits_per_100_tokens")
    if hits is not None:
        summary["key_metrics"]["Politeness marker hits"] = str(int(hits))
    if rate is not None:
        summary["key_metrics"]["Politeness hits / 100 tokens"] = f"{float(rate):.2f}"
    soft = global_stats.get("soft_request_ratio")
    if soft is not None:
        summary["key_metrics"]["Soft request ratio"] = f"{float(soft):.3f}"
    summary.setdefault("highlights", []).append(
        "Politeness markers are lexical; interactional power remains in interactions equity."
    )


register_extractor("politeness", extract_politeness_summary)
