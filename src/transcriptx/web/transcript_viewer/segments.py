"""Transcript segment renderers."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from transcriptx.utils.text_utils import format_time_detailed
from transcriptx.web.transcript_viewer.highlight import render_highlight_html


def _format_single_timestamp(seconds: float, format_key: str) -> str:
    if format_key == "seconds" and seconds < 60:
        return f"{seconds:.1f}s"
    return format_time_detailed(seconds)


def _format_timestamp_range(start: float, end: float, format_key: str) -> str:
    return (
        f"{_format_single_timestamp(start, format_key)}"
        f" - {_format_single_timestamp(end, format_key)}"
    )


def group_segments_by_speaker(
    display_segments: list[tuple[int, dict[str, Any]]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group contiguous display segments by speaker."""
    speaker_groups: list[tuple[str, list[dict[str, Any]]]] = []
    current_speaker: str | None = None
    current_group: list[dict[str, Any]] = []
    for _, segment in display_segments:
        speaker = segment.get("speaker_display") or segment.get("speaker", "Unknown")
        if speaker != current_speaker:
            if current_group:
                speaker_groups.append((str(current_speaker), current_group))
            current_speaker = str(speaker)
            current_group = [segment]
        else:
            current_group.append(segment)
    if current_group:
        speaker_groups.append((str(current_speaker), current_group))
    return speaker_groups


def render_plain_segments(
    display_segments: list[tuple[int, dict[str, Any]]],
    *,
    show_timestamps: bool,
    format_key: str,
    highlight_query: str | None,
    jump_index: int | None,
) -> None:
    """Render transcript segments in plain reading mode."""
    copy_chunks: list[str] = []
    for segment_index, segment in display_segments:
        speaker = segment.get("speaker_display") or segment.get("speaker", "Unknown")
        text = str(segment.get("text", ""))
        copy_chunks.append(text)
        start = segment.get("start", 0)
        end = segment.get("end", 0)
        rendered_text = text
        if highlight_query and segment_index == jump_index:
            rendered_text = render_highlight_html(text, highlight_query)
        chip = f'<span class="tx-speaker-chip">{html.escape(str(speaker))}</span>'
        if show_timestamps:
            timestamp = _format_timestamp_range(float(start), float(end), format_key)
            st.markdown(
                f"{chip} · ⏱️ {html.escape(timestamp)}",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(chip, unsafe_allow_html=True)
        st.markdown('<div class="tx-segment-block">', unsafe_allow_html=True)
        if rendered_text != text:
            st.markdown(rendered_text, unsafe_allow_html=True)
        else:
            st.write(text)
        st.markdown("</div>", unsafe_allow_html=True)
        st.divider()
    if copy_chunks:
        joined = "\n\n".join(copy_chunks)
        st.download_button(
            "Download visible segments as .txt",
            data=joined,
            file_name="transcript_snippet.txt",
            mime="text/plain",
            key="transcript_copy_visible_txt",
        )


def render_segmented_tab(
    display_segments: list[tuple[int, dict[str, Any]]],
    *,
    show_timestamps: bool,
    format_key: str,
) -> None:
    """Render transcript segments grouped by contiguous speakers."""
    speaker_groups = group_segments_by_speaker(display_segments)
    for speaker_name, group_segments in speaker_groups:
        group_start = group_segments[0].get("start", 0)
        group_end = group_segments[-1].get("end", 0)
        if show_timestamps:
            group_timestamp = _format_timestamp_range(
                float(group_start), float(group_end), format_key
            )
            expander_title = f"🎤 {speaker_name} ({len(group_segments)} segments) · ⏱️ {group_timestamp}"
        else:
            expander_title = f"🎤 {speaker_name} ({len(group_segments)} segments)"
        with st.expander(expander_title, expanded=True):
            for segment in group_segments:
                text = segment.get("text", "")
                st.write(text)
                if "sentiment" in segment:
                    sentiment = segment["sentiment"]
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.caption(f"Sentiment: {sentiment.get('compound', 0):.2f}")
                    with col2:
                        st.caption(f"Positive: {sentiment.get('pos', 0):.2f}")
                    with col3:
                        st.caption(f"Negative: {sentiment.get('neg', 0):.2f}")
                if "emotion" in segment:
                    st.caption(f"Emotion: {segment['emotion']}")
