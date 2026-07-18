"""Legacy emotion artifact readers — UI/report only; never feed analysis consumers."""

from __future__ import annotations

from typing import Any, Mapping


def is_legacy_emotion_artifact(payload: Mapping[str, Any]) -> bool:
    if payload.get("schema_version"):
        return False
    # Pre-v2 often has emotions score dict or context_emotion_source
    if "context_emotion_source" in payload or "emotions" in payload:
        return True
    if "global_stats" in payload and "semantics_version" not in payload:
        return True
    return False


def project_legacy_for_ui(payload: Mapping[str, Any]) -> dict[str, Any]:
    """
    Read-only UI projection of pre-v2 emotion artifacts.

    Preserves NRC provenance for any context_emotion_* fields.
    Must never be treated as contextual_emotion module output.
    """
    source = payload.get("context_emotion_source")
    return {
        "legacy": True,
        "schema_version": None,
        "semantics_version": "emotion_lexical_v1_legacy",
        "ui_only": True,
        "analysis_consumer_forbidden": True,
        "context_emotion_source": source or "nrc",
        "provenance_note": (
            "Legacy NRC-derived context_emotion_* fields are UI/report-only. "
            "Re-run emotion (lexical v2) and contextual_emotion for analysis consumers."
        ),
        "global_stats": payload.get("global_stats") or payload.get("emotions") or {},
        "speaker_stats": payload.get("speaker_stats") or {},
        "nrc_scores": payload.get("nrc_scores") or {},
    }
