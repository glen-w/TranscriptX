"""
Subject header component for the Web UI.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web.services.subject_service import ResolvedSubject


def render_subject_header(subject: ResolvedSubject) -> None:
    col_left, col_right = st.columns([4, 1])
    with col_left:
        st.markdown(f"### {subject.display.name}")
    with col_right:
        st.markdown(
            f"<div style='text-align:right;'><span style='padding:4px 8px;border-radius:8px;background:#eef2ff;font-size:0.85rem;'>{subject.display.badge}</span></div>",
            unsafe_allow_html=True,
        )
    if subject.subject_type == "group":
        label = f"{subject.display.member_count} members"
        with st.expander(label, expanded=False):
            for member in subject.members:
                name = member.file_name or member.file_path or "(unknown)"
                st.write(f"- {name}")
