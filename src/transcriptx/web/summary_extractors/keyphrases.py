"""Summary extractor for keyphrases."""

from typing import Any, Dict

from . import register_extractor


def extract_keyphrases_summary(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    if data.get("usable") is False:
        summary.setdefault("highlights", []).append(
            "Keyphrases abstained (unsupported language, skipped methods, or empty usable result)."
        )
        return
    methods_run = data.get("methods_run") or []
    if isinstance(methods_run, list) and methods_run:
        summary["key_metrics"]["Keyphrase methods"] = ", ".join(
            str(m) for m in methods_run
        )
    gbm = data.get("global_by_method") or {}
    phrase_count = 0
    if isinstance(gbm, dict):
        nc = gbm.get("noun_chunks")
        if isinstance(nc, dict):
            phrases = nc.get("phrases") or []
            if isinstance(phrases, list):
                phrase_count = len(phrases)
    if phrase_count:
        summary["key_metrics"]["Keyphrases (noun chunks)"] = str(phrase_count)
        top = None
        nc = gbm.get("noun_chunks") if isinstance(gbm, dict) else None
        if isinstance(nc, dict):
            phrases = nc.get("phrases") or []
            if phrases and isinstance(phrases[0], dict):
                top = phrases[0].get("phrase")
        if top:
            summary.setdefault("highlights", []).append(f"Top keyphrase: {top}")
    summary.setdefault("highlights", []).append(
        "Keyphrases rank multiword salience per method; noun_chunks is the primary Insights view."
    )


register_extractor("keyphrases", extract_keyphrases_summary)
