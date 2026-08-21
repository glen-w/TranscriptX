"""
Streamlit UI for serial/split recording detection warnings.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.core.audio.serial_groups import SerialGroup
from transcriptx.web.components.info_tooltip import widget_help

DurationLookup = Callable[[Path], Optional[float]]


@dataclass(frozen=True)
class SerialGroupPromptState:
    """User choices from the serial-group prompt."""

    transcribe_separately_ok: bool
    merge_and_transcribe_clicked: bool
    review_in_merge_clicked: bool


def _format_duration(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "—"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def render_serial_group_prompt(
    groups: list[SerialGroup],
    *,
    separate_ok_key: str,
    merge_button_key: str,
    review_button_key: str,
    duration_lookup: DurationLookup | None = None,
) -> SerialGroupPromptState:
    """
    Render warning and actions when serial audio groups are detected.

    Caller handles merge/transcription logic; this component only renders UI.
    """
    st.warning(
        "These files look like **parts of one recording**. Transcribing them "
        "separately will create **separate transcripts**. Merging first is "
        "recommended for **one unified transcript**. Order is based on filename "
        "indices; merge via **Workflow → Audio Preprocessing → Auto-merge** "
        "before transcription."
    )

    for group in groups:
        extension = group.ordered_paths[0].suffix.lower() if group.ordered_paths else ""
        total_duration: Optional[float] = None
        if duration_lookup is not None:
            parts = [duration_lookup(p) for p in group.ordered_paths]
            if all(d is not None for d in parts):
                total_duration = sum(d for d in parts if d is not None)

        st.markdown(
            f"**{group.base_key}** · {len(group.ordered_paths)} files · "
            f"`{extension}` · {group.rule_label} · "
            f"confidence **{group.confidence}**"
        )
        if total_duration is not None:
            st.caption(
                f"Combined duration (approx.): {_format_duration(total_duration)}"
            )
        for path in group.ordered_paths:
            st.text(f"  {path.name}")
        for warning in group.warnings:
            st.caption(f"⚠ {warning}")

    col_merge, col_review = st.columns(2)
    with col_merge:
        merge_clicked = st.button(
            "Merge detected groups and transcribe",
            type="primary",
            icon=ic.MERGE,
            key=merge_button_key,
        )
    with col_review:
        review_clicked = st.button(
            "Open Audio Preprocessing",
            key=review_button_key,
            icon=ic.GRAPHIC_EQ,
        )

    separate_ok = st.checkbox(
        "Transcribe these files separately anyway",
        value=st.session_state.get(separate_ok_key, False),
        key=separate_ok_key,
        help=widget_help(
            (
                "Split recorder files are normally merged before transcription. "
                "Merge concatenates only unless you enable preprocessing on the "
                "Auto-merge or Manual merge form."
            )
        ),
    )

    return SerialGroupPromptState(
        transcribe_separately_ok=separate_ok,
        merge_and_transcribe_clicked=merge_clicked,
        review_in_merge_clicked=review_clicked,
    )
