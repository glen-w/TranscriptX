"""Summary extractor for fine-grained emotion (experimental)."""

from __future__ import annotations

from typing import Any, Dict

from . import register_extractor


def extract_fine_grained_emotion_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    summary.setdefault("highlights", []).append(
        "Fine-grained emotion is exploratory and domain-dependent."
    )
    summary["key_metrics"]["Channel"] = data.get("release_channel", "experimental")
    summary["key_metrics"]["Run status"] = data.get("run_status", "unknown")
    summary["key_metrics"]["Usable output"] = bool(data.get("usable_output"))
    summary["key_metrics"]["Segments scored"] = int(data.get("segments_scored") or 0)
    summary["key_metrics"]["Segments failed"] = int(data.get("segments_failed") or 0)
    rates = data.get("primary_rates") or {}
    for k, v in rates.items():
        summary["key_metrics"][k] = f"{float(v):.2f}"
    conf = data.get("confidence_summary") or {}
    if conf.get("n"):
        summary["key_metrics"][
            "Mean confidence"
        ] = f"{float(conf.get('mean') or 0):.2f}"
    prevalence = data.get("native_label_prevalence") or {}
    if prevalence:
        top = sorted(prevalence.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        summary.setdefault("highlights", []).append(
            "Native label prevalence: " + ", ".join(f"{k} ({v})" for k, v in top)
        )
    speaker_stats = data.get("speaker_stats") or {}
    if speaker_stats:
        summary["key_metrics"]["Speakers with labels"] = len(speaker_stats)
    for w in (data.get("warnings") or [])[:2]:
        summary.setdefault("highlights", []).append(str(w))


register_extractor("fine_grained_emotion", extract_fine_grained_emotion_summary)
