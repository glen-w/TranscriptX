"""Run Analysis / Batch picker for custom questions."""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from transcriptx.core.analysis.llm_custom_qa.normalize import normalize_questions
from transcriptx.core.analysis.llm_custom_qa.resolve import (
    EffectiveCustomQAQuestions,
    normalize_library_questions,
    resolve_effective_custom_qa_questions,
)
from transcriptx.core.config.persistence import patch_project_config_keys
from transcriptx.core.utils.config import get_config


def render_custom_qa_picker(
    *,
    key_prefix: str,
    module_selected: bool,
) -> tuple[Optional[list[str]], Optional[EffectiveCustomQAQuestions]]:
    """Render question picker before the model selector.

    Returns ``(request_questions, effective)`` where:
    - ``request_questions`` is what to put on AnalysisRequest
      (None → library; [] → explicit empty; list → request)
    - ``effective`` is the resolved immutable object (or None if module not selected)
    """
    if not module_selected:
        return None, None

    cfg = get_config().analysis.llm_custom_qa
    saved = list(getattr(cfg, "saved_questions", []) or [])
    max_per_run = int(getattr(cfg, "max_questions_per_run", 8))

    st.markdown("#### Custom questions")
    st.caption(
        "Select library questions and/or add ad-hoc lines for this run. "
        "Leave empty and choose explicit empty to skip answering."
    )

    selected_saved: list[str] = []
    if saved:
        selected_saved = st.multiselect(
            "From library",
            options=saved,
            default=[],
            key=f"{key_prefix}_saved",
            max_selections=max_per_run,
        )
    else:
        st.caption("No saved questions yet — add some in Settings → Questions.")

    adhoc = st.text_area(
        "Ad-hoc questions (one per line)",
        value="",
        key=f"{key_prefix}_adhoc",
        height=100,
    )
    explicit_empty = st.checkbox(
        "Run with no questions (empty Q success artifact)",
        value=False,
        key=f"{key_prefix}_explicit_empty",
    )
    save_for_later = st.checkbox(
        "Save new ad-hoc questions to library after launch",
        value=False,
        key=f"{key_prefix}_save_later",
    )

    if explicit_empty:
        effective = resolve_effective_custom_qa_questions(
            request_questions=[],
            request_field_present=True,
            settings=cfg,
        )
        return [], effective

    lines = [line.strip() for line in (adhoc or "").splitlines() if line.strip()]
    combined = list(selected_saved) + lines
    if not combined:
        # Omitted → library (may still be empty library)
        effective = resolve_effective_custom_qa_questions(
            request_questions=None,
            request_field_present=False,
            settings=cfg,
        )
        st.session_state[f"{key_prefix}_save_for_later_payload"] = (
            lines if save_for_later else None
        )
        return None, effective

    try:
        normalised = normalize_questions(
            combined,
            max_questions=max_per_run,
            max_question_chars=int(cfg.max_question_chars),
            max_total_question_chars=int(cfg.max_run_total_question_chars),
        )
    except Exception as exc:
        st.error(f"Invalid questions: {exc}")
        effective = resolve_effective_custom_qa_questions(
            request_questions=[],
            request_field_present=True,
            settings=cfg,
        )
        return [], effective

    effective = resolve_effective_custom_qa_questions(
        request_questions=list(normalised),
        request_field_present=True,
        settings=cfg,
    )
    st.session_state[f"{key_prefix}_save_for_later_payload"] = (
        lines if save_for_later else None
    )
    return list(normalised), effective


def maybe_save_questions_for_later(*, key_prefix: str) -> None:
    """Append ad-hoc questions to the project library under FileLock."""
    payload = st.session_state.pop(f"{key_prefix}_save_for_later_payload", None)
    if not payload:
        return
    cfg = get_config().analysis.llm_custom_qa
    existing = list(getattr(cfg, "saved_questions", []) or [])
    merged = existing + list(payload)
    try:
        normalised = normalize_library_questions(merged, settings=cfg)
    except Exception as exc:
        st.warning(f"Could not save questions to library: {exc}")
        return
    patch_project_config_keys(
        {
            "analysis": {
                "llm_custom_qa": {
                    "saved_questions": list(normalised),
                }
            }
        }
    )
    st.toast(f"Saved {len(payload)} question(s) to library")
