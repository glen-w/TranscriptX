"""Settings → Questions panel for the project question library."""

from __future__ import annotations

import streamlit as st

from transcriptx.core.analysis.llm_custom_qa.resolve import normalize_library_questions
from transcriptx.core.config.persistence import patch_project_config_keys
from transcriptx.core.utils.config import get_config


def render_questions_panel() -> None:
    """Full editor for analysis.llm_custom_qa.saved_questions."""
    st.subheader("Question library")
    st.caption(
        "Reusable questions for the Custom Questions (`llm_custom_qa`) module. "
        "Run Analysis can select from this library or add ad-hoc questions."
    )
    cfg = get_config().analysis.llm_custom_qa
    saved = list(getattr(cfg, "saved_questions", []) or [])
    text = st.text_area(
        "Questions (one per line)",
        value="\n".join(saved),
        height=240,
        key="settings_questions_library",
    )
    col1, col2 = st.columns(2)
    with col1:
        st.caption(
            f"Limits: {cfg.max_library_questions} questions, "
            f"{cfg.max_library_total_question_chars} total chars, "
            f"{cfg.max_question_chars} chars each."
        )
    with col2:
        if st.button("Save library", type="primary", key="settings_questions_save"):
            lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
            try:
                normalised = normalize_library_questions(lines, settings=cfg)
            except Exception as exc:
                st.error(f"Invalid library: {exc}")
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
            # Keep process-local config in sync (no global reload_config API).
            cfg.saved_questions = list(normalised)
            st.success(f"Saved {len(normalised)} question(s).")
            st.rerun()
