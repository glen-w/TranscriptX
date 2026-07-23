"""Transcript segment renderers."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Mapping

import streamlit as st

from transcriptx.export.grouping import segment_speaker_label
from transcriptx.services.speaker_studio.segment_index import SegmentInfo
from transcriptx.utils.text_utils import format_time_detailed
from transcriptx.web.components.playback_panel import set_active_clip
from transcriptx.web.speaker_accent import speaker_meta_line_html
from transcriptx.web.transcript_viewer.highlight import render_highlight_html
from transcriptx.web.transcript_viewer.playback_targets import (
    format_safe_timestamp_range,
    group_timestamp_bounds,
)


@dataclass(frozen=True)
class TranscriptPlaybackBinding:
    """Playback wiring shared by Turns and Segments tabs.

    ``targets`` maps original transcript source index → validated SegmentInfo.
    ``play_key`` is the shared session-state key for the active source index.
    ``owner_prefix`` namespaces widget keys (session/run/path identity).
    """

    enabled: bool
    targets: Mapping[int, SegmentInfo]
    play_key: str
    owner_prefix: str


def play_button_eligible(
    binding: TranscriptPlaybackBinding | None, source_index: int
) -> bool:
    """True when a ▶ control should be rendered for this source index."""
    return bool(binding and binding.enabled and source_index in binding.targets)


def play_button_key(binding: TranscriptPlaybackBinding, tab: str, source_index: int) -> str:
    """Deterministic widget key: owner + tab + source index (never filtered ordinal)."""
    return f"tx_play|{binding.owner_prefix}|{tab}|{source_index}"


def _format_single_timestamp(seconds: float, format_key: str) -> str:
    if format_key == "seconds" and seconds < 60:
        return f"{seconds:.1f}s"
    return format_time_detailed(seconds)


def _format_timestamp_range(start: float, end: float, format_key: str) -> str:
    return (
        f"{_format_single_timestamp(start, format_key)}"
        f" - {_format_single_timestamp(end, format_key)}"
    )


def _safe_display_timestamp_range(
    start: object, end: object, format_key: str
) -> str | None:
    """Omit invalid timestamps instead of crashing the viewer."""
    return format_safe_timestamp_range(
        start, end, format_key, format_single=_format_single_timestamp
    )


def group_segments_by_speaker(
    display_segments: list[tuple[int, dict[str, Any]]],
) -> list[tuple[str, list[tuple[int, dict[str, Any]]]]]:
    """Group contiguous display segments by speaker, preserving source indices.

    Does not modify the shared export grouping contract; this is UI-only.
    """
    groups: list[tuple[str, list[tuple[int, dict[str, Any]]]]] = []
    current_speaker: str | None = None
    current_group: list[tuple[int, dict[str, Any]]] = []
    for source_index, segment in display_segments:
        if not isinstance(segment, dict):
            continue
        speaker = segment_speaker_label(segment)
        if speaker != current_speaker:
            if current_group:
                groups.append((str(current_speaker), current_group))
            current_speaker = speaker
            current_group = [(source_index, segment)]
        else:
            current_group.append((source_index, segment))
    if current_group:
        groups.append((str(current_speaker), current_group))
    return groups


def _render_play_button(
    binding: TranscriptPlaybackBinding | None,
    *,
    tab: str,
    source_index: int,
) -> None:
    if not play_button_eligible(binding, source_index):
        return
    assert binding is not None  # for type checkers; guarded above
    st.button(
        "▶",
        key=play_button_key(binding, tab, source_index),
        help="Play this clip",
        on_click=set_active_clip,
        args=(binding.play_key, source_index),
    )


def _turn_block_html(
    *,
    header_html: str,
    body_html: str,
    jump: bool = False,
) -> str:
    block_class = "tx-turn"
    if jump:
        block_class += " tx-turn--jump"
    return (
        f'<div class="{block_class}">'
        f"{header_html}"
        f'<div class="tx-turn-body">{body_html}</div>'
        f"</div>"
    )


def render_plain_segments(
    display_segments: list[tuple[int, dict[str, Any]]],
    *,
    show_timestamps: bool,
    format_key: str,
    highlight_query: str | None,
    jump_index: int | None,
    playback: TranscriptPlaybackBinding | None = None,
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
        is_jump_target = jump_index is not None and segment_index == jump_index
        if highlight_query and is_jump_target:
            rendered_text = render_highlight_html(text, highlight_query)
        marker = (
            ' <span class="tx-jump-target">Selected</span>' if is_jump_target else ""
        )
        timestamp = None
        if show_timestamps:
            timestamp = _safe_display_timestamp_range(start, end, format_key)
        header = speaker_meta_line_html(
            speaker, timestamp=timestamp, marker_html=marker
        )
        body = rendered_text if rendered_text != text else html.escape(text)
        if play_button_eligible(playback, segment_index):
            st.markdown(
                _turn_block_html(
                    header_html=header, body_html="", jump=is_jump_target
                ),
                unsafe_allow_html=True,
            )
            col_text, col_play = st.columns([20, 1])
            with col_text:
                if rendered_text != text:
                    st.markdown(rendered_text, unsafe_allow_html=True)
                else:
                    st.write(text)
            with col_play:
                _render_play_button(playback, tab="segments", source_index=segment_index)
        else:
            st.markdown(
                _turn_block_html(
                    header_html=header, body_html=body, jump=is_jump_target
                ),
                unsafe_allow_html=True,
            )
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
    playback: TranscriptPlaybackBinding | None = None,
) -> None:
    """Render contiguous speaker turns with a compact name · time header."""
    speaker_groups = group_segments_by_speaker(display_segments)
    for speaker_name, group_segments in speaker_groups:
        timestamp = None
        if show_timestamps:
            bounds = group_timestamp_bounds(group_segments)
            if bounds is not None:
                timestamp = _format_timestamp_range(bounds[0], bounds[1], format_key)
        header = speaker_meta_line_html(speaker_name, timestamp=timestamp)
        body_parts = [
            html.escape(str(segment.get("text", "")))
            for _, segment in group_segments
        ]
        # Prefer a single markdown block so Streamlit does not insert large gaps.
        has_play = any(
            play_button_eligible(playback, source_index)
            for source_index, _ in group_segments
        )
        has_extras = any(
            ("sentiment" in segment) or ("emotion" in segment)
            for _, segment in group_segments
        )
        if not has_play and not has_extras:
            st.markdown(
                _turn_block_html(
                    header_html=header,
                    body_html="<br/>".join(body_parts),
                ),
                unsafe_allow_html=True,
            )
            continue

        st.markdown(
            _turn_block_html(header_html=header, body_html=""),
            unsafe_allow_html=True,
        )
        for source_index, segment in group_segments:
            text = segment.get("text", "")
            if play_button_eligible(playback, source_index):
                col_text, col_play = st.columns([20, 1])
                with col_text:
                    st.write(text)
                with col_play:
                    _render_play_button(
                        playback, tab="turns", source_index=source_index
                    )
            else:
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
