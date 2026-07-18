"""Summary extractor for lexical emotion v2."""

from __future__ import annotations

from typing import Any, Dict

from . import register_extractor


def extract_emotion_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Extract summary from lexical emotion analysis data."""
    if data.get("ui_copy"):
        summary.setdefault("highlights", []).append(str(data["ui_copy"]))

    summary["key_metrics"]["Run status"] = data.get("run_status", "unknown")
    summary["key_metrics"]["Usable output"] = bool(data.get("usable_output"))
    summary["key_metrics"]["Segments scored"] = int(data.get("segments_scored") or 0)

    global_stats = data.get("global_stats") or {}
    scores = global_stats.get("emotion_scores") or data.get("emotions") or {}
    if isinstance(scores, dict):
        numeric = {
            k: float(v)
            for k, v in scores.items()
            if isinstance(v, (int, float))
            and k
            not in {
                "assignment_counts",
                "valence_scores",
                "emotion_scores",
                "valence_assignment_counts",
            }
        }
        if numeric:
            top = sorted(numeric.items(), key=lambda kv: kv[1], reverse=True)[:3]
            summary["key_metrics"]["Top vocabulary categories"] = ", ".join(
                f"{k}={v:.2f}" for k, v in top
            )

    for w in (data.get("warnings") or [])[:3]:
        summary.setdefault("highlights", []).append(f"Warning: {w}")


register_extractor("emotion", extract_emotion_summary)
