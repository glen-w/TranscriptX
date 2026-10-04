"""Question library picker for the RAG Ask page (Settings → Questions)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from transcriptx.core.analysis.llm_custom_qa.request_questions import (
    structured_library_from_settings,
)
from transcriptx.core.utils.config import get_config
from transcriptx.web import icons as ic
from transcriptx.web.components.info_tooltip import widget_help


def filter_global_scope_library_questions(
    questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Library entries marked Global (whole transcript / group in Custom Questions)."""
    out: list[dict[str, Any]] = []
    for q in questions:
        text = str(q.get("text") or "").strip()
        if not text:
            continue
        scopes = q.get("scopes") or {}
        if scopes.get("global"):
            out.append({"text": text, "scopes": dict(scopes)})
    return out


def library_question_label(q: dict[str, Any]) -> str:
    text = str(q.get("text") or "").strip()
    scopes = q.get("scopes") or {}
    return (
        f"{text[:80]} [{'G' if scopes.get('global') else ''}"
        f"{'S' if scopes.get('per_speaker') else ''}]"
    )


def render_ask_global_library_picker() -> list[str]:
    """
    Multiselect from the project question library (global scope only).

    Returns question texts when the user clicks **Ask selected** on this run.
    """
    cfg = get_config().analysis.llm_custom_qa
    saved = filter_global_scope_library_questions(
        structured_library_from_settings(cfg)
    )
    max_per_run = int(getattr(cfg, "max_questions_per_run", 8))

    st.markdown("#### Question library")
    st.caption(
        "Global questions from **Settings → Questions** (same library as Custom Questions). "
        "Per-speaker library entries are not listed here — use Run Analysis for those."
    )

    if not saved:
        st.info("No global questions saved yet. Add them under Settings → Questions.")
        return []

    labels = [library_question_label(q) for q in saved]
    label_to_text = {labels[i]: saved[i]["text"] for i in range(len(saved))}

    selected_labels = st.multiselect(
        "Global questions",
        options=labels,
        default=[],
        key="ask_rag_library_multiselect",
        max_selections=max_per_run,
        help=widget_help("Pick one or more saved questions to run against this transcript."),
    )

    if not st.button(
        "Ask selected",
        icon=ic.PLAY,
        key="ask_rag_library_run",
        disabled=not selected_labels,
    ):
        return []

    return [label_to_text[lab] for lab in selected_labels if lab in label_to_text]
