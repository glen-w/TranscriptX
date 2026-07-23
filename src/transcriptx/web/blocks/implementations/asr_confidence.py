"""Insights/Data block: ASR confidence review with open-in-transcript."""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.implementations.insights import (
    _loader,
    _render_open_in_transcript_button,
    _render_quiet_module_empty,
)
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.utils.text_utils import format_time_detailed
from transcriptx.web.speaker_accent import speaker_inline_html


def _render_span_rows(
    *,
    title: str,
    rows: List[Dict[str, Any]],
    session_slug: str | None,
    run_id: str | None,
    key_prefix: str,
) -> None:
    if not rows:
        st.caption(f"No {title.lower()} emitted.")
        return
    st.markdown(f"**{title}**")
    for index, row in enumerate(rows):
        start = row.get("start")
        end = row.get("end")
        mean = row.get("mean_score")
        speaker = row.get("speaker") or "—"
        preview = str(row.get("text_preview") or "").strip()
        time_range = "—"
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            time_range = (
                f"{format_time_detailed(float(start))}"
                f"-{format_time_detailed(float(end))}"
            )
        mean_s = f"{float(mean):.3f}" if isinstance(mean, (int, float)) else "—"
        speaker_label = str(speaker).strip()
        speaker_html = (
            speaker_inline_html(speaker_label)
            if speaker_label and speaker_label != "—"
            else ""
        )
        if speaker_html:
            st.markdown(
                f"{speaker_html} · {time_range} · mean score {mean_s}",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"**{speaker_label or '—'}** · {time_range} · mean score {mean_s}")
        if preview:
            st.write(preview)
        playback = row.get("playback") or {}
        segment_index = playback.get("segment_index")
        if segment_index is None:
            segment_index = row.get("segment_index_start")
        start_time = playback.get("start", start)
        _render_open_in_transcript_button(
            session_slug=session_slug,
            run_id=run_id,
            segment_index=segment_index if isinstance(segment_index, int) else None,
            start_time=(
                float(start_time) if isinstance(start_time, (int, float)) else None
            ),
            quote=preview,
            button_key=f"{key_prefix}_{index}",
        )


def render_asr_confidence(ctx: BlockContext, _placement: BlockPlacement) -> None:
    """Render ASR confidence summary, spans, and clusters with playback links."""
    loader = _loader(ctx)
    run_root = ctx.run_root

    if loader is None:
        _render_quiet_module_empty(
            label="ASR confidence",
            run_root=run_root,
            module="transcript_quality",
            empty_hint="Run transcript_quality to see ASR confidence diagnostics.",
            ctx=ctx,
            key="asr_confidence_empty",
        )
        return

    payload = loader.load_json("transcript_quality", "_transcript_quality.json")
    if not payload:
        _render_quiet_module_empty(
            label="ASR confidence",
            run_root=run_root,
            module="transcript_quality",
            empty_hint="Run transcript_quality to see ASR confidence diagnostics.",
            ctx=ctx,
            key="asr_confidence_missing",
        )
        return

    disclaimer = payload.get("disclaimer")
    if disclaimer:
        st.caption(str(disclaimer))

    asr = payload.get("asr_confidence") or {}
    provenance = payload.get("provenance") or {}
    status = asr.get("status") or "absent"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", str(status))
    cov = asr.get("coverage_ratio")
    c2.metric(
        "Coverage",
        f"{float(cov):.0%}" if isinstance(cov, (int, float)) else "—",
    )
    mean = asr.get("mean_score")
    c3.metric(
        "Mean score",
        f"{float(mean):.3f}" if isinstance(mean, (int, float)) else "—",
    )
    low = asr.get("low_score_ratio")
    c4.metric(
        "Low-score ratio",
        f"{float(low):.0%}" if isinstance(low, (int, float)) else "—",
    )

    with st.expander("Provenance and diagnostics", expanded=False):
        st.json(
            {
                "provenance": provenance,
                "eligible_word_count": asr.get("eligible_word_count"),
                "scored_word_count": asr.get("scored_word_count"),
                "missing_score_count": asr.get("missing_score_count"),
                "invalid_score_count": asr.get("invalid_score_count"),
                "out_of_range_score_count": asr.get("out_of_range_score_count"),
                "excluded_unusable_count": asr.get("excluded_unusable_count"),
                "score_normalisation": asr.get("score_normalisation"),
                "spans_total_count": asr.get("spans_total_count"),
                "spans_emitted_count": asr.get("spans_emitted_count"),
                "clusters_total_count": asr.get("clusters_total_count"),
                "clusters_emitted_count": asr.get("clusters_emitted_count"),
            }
        )

    if status == "absent":
        st.info(
            "No accepted word-level ASR confidence scores on this transcript. "
            "This module does not invent scores for imports without word scores."
        )
        return

    _render_span_rows(
        title="Low-confidence clusters",
        rows=list(asr.get("clusters") or []),
        session_slug=ctx.subject_id,
        run_id=ctx.run_id,
        key_prefix="asr_cluster",
    )
    _render_span_rows(
        title="Low-confidence spans",
        rows=list(asr.get("spans") or []),
        session_slug=ctx.subject_id,
        run_id=ctx.run_id,
        key_prefix="asr_span",
    )
