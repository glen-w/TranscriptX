"""Minimal context line: subject, optional type, run — no page label or jump row."""

from __future__ import annotations

import html
from typing import Any, Mapping

import streamlit as st

from transcriptx.web.services import SubjectService


def render_context_bar(session_state: Mapping[str, Any]) -> None:
    subject = SubjectService.resolve_current_subject(dict(session_state))
    run_id = session_state.get("run_id")

    parts: list[str] = []
    if subject:
        parts.append(html.escape(subject.display.name))
        parts.append("Transcript" if subject.subject_type == "transcript" else "Group")
    else:
        parts.append("No subject")

    if run_id:
        parts.append(html.escape(str(run_id)))
    else:
        parts.append("No run")

    line = " · ".join(parts)

    st.markdown('<div class="tx-context-bar-wrap">', unsafe_allow_html=True)
    st.markdown(
        '<div class="tx-context-bar-inner">'
        f'<span class="tx-context-line">{line}</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
