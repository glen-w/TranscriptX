"""Minimal context line: human-readable subject and run with raw-id info control."""

from __future__ import annotations

import html
from typing import Any, Mapping

import streamlit as st

from transcriptx.web.components.run_id_info import build_run_id_info_html
from transcriptx.web.context_format import (
    format_context_line,
    friendly_subject_label,
)
from transcriptx.web.services import SubjectService
from transcriptx.web.state import RUN_ID_KEY, SUBJECT_ID_KEY, SUBJECT_TYPE_KEY


def _cheap_slug_labels() -> dict[str, str]:
    try:
        from transcriptx.web.sidebar_options import _slug_display_labels_from_index

        return dict(_slug_display_labels_from_index())
    except Exception:
        return {}


def render_context_bar(session_state: Mapping[str, Any]) -> None:
    subject_type = session_state.get(SUBJECT_TYPE_KEY)
    subject_id = session_state.get(SUBJECT_ID_KEY)
    run_id = session_state.get(RUN_ID_KEY)

    canonical_type = subject_type if subject_type in ("transcript", "group") else None
    display_name: str | None = None
    stem: str | None = None

    subject = SubjectService.resolve_current_subject(dict(session_state))
    if subject is not None:
        display_name = subject.display.name
        if canonical_type is None:
            canonical_type = subject.subject_type

    slug_labels = _cheap_slug_labels() if canonical_type == "transcript" else None
    subject_label = friendly_subject_label(
        canonical_type,
        subject_id=str(subject_id) if subject_id else None,
        slug_labels=slug_labels,
        display_name=display_name,
        stem=stem,
    )

    presentation = format_context_line(
        subject_type=canonical_type,
        subject_label=subject_label,
        run_id=str(run_id) if run_id else None,
    )

    escaped_primary = html.escape(presentation.primary_text)
    info_html = ""
    if presentation.raw_run_id:
        info_html = " " + build_run_id_info_html(
            presentation.raw_run_id, control_id="tx-context-run-tip"
        )

    # Single markdown so wrap styles apply to the line (not an empty sticky strip).
    st.markdown(
        '<div class="tx-context-bar-wrap">'
        '<div class="tx-context-bar-inner">'
        f'<span class="tx-context-line">{escaped_primary}</span>'
        f"{info_html}"
        "</div></div>",
        unsafe_allow_html=True,
    )
