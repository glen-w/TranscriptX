"""Streamlit rendering for speaker exemplars."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any, Dict, Optional

import streamlit as st

from transcriptx.core.analysis.exemplars import (
    SegmentRecord,
    SpeakerExemplarsConfig,
    compute_speaker_exemplars,
)
from transcriptx.core.config import resolve_effective_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.utils.text_utils import format_time_detailed
from transcriptx.web.db_utils import (
    get_other_segments_for_transcript,
    get_speaker_segments_for_transcript,
    get_transcript_file_for_run,
    get_transcript_revision_signal,
)
from transcriptx.web.services import RunIndex, SubjectService

logger = get_logger()


def _config_from_dict(raw: Dict[str, Any]) -> SpeakerExemplarsConfig:
    if "tfidf_ngram_range" in raw and isinstance(raw["tfidf_ngram_range"], list):
        raw["tfidf_ngram_range"] = tuple(raw["tfidf_ngram_range"])
    return SpeakerExemplarsConfig(**raw)


def _segment_to_record(segment: Any) -> SegmentRecord:
    return SegmentRecord(
        segment_id=segment.id,
        segment_index=segment.segment_index,
        speaker_id=str(segment.speaker_id),
        text=segment.text or "",
        word_count=segment.word_count,
        start_time=segment.start_time,
        end_time=segment.end_time,
    )


def _format_time(start: Optional[float], end: Optional[float]) -> str:
    if start is None or end is None:
        return ""
    return f"{format_time_detailed(start)} - {format_time_detailed(end)}"


@st.cache_data(show_spinner=False)
def _compute_cached(
    speaker_id: int,
    transcript_file_id: int,
    run_id: str,
    config_payload: str,
    refresh_nonce: int,
    revision_key: Optional[str],
) -> Dict[str, Any]:
    config_dict = json.loads(config_payload)
    config = _config_from_dict(config_dict)
    speaker_segments = get_speaker_segments_for_transcript(
        speaker_id=speaker_id,
        transcript_file_id=transcript_file_id,
        limit=config.max_segments_considered,
    )
    other_segments = get_other_segments_for_transcript(
        speaker_id=speaker_id,
        transcript_file_id=transcript_file_id,
        max_other_speakers=config.distinctive_max_other_speakers,
        max_other_segments_total=config.distinctive_max_other_segments_total,
        max_other_segments_per_speaker=config.distinctive_max_other_segments_per_speaker,
    )
    results = compute_speaker_exemplars(
        segments=[_segment_to_record(seg) for seg in speaker_segments],
        other_segments=[_segment_to_record(seg) for seg in other_segments],
        config=config,
    )
    return {
        "combined": [asdict(item) for item in results.combined],
        "per_method": {
            name: [asdict(item) for item in items]
            for name, items in results.per_method.items()
        },
        "metadata": results.metadata,
        "run_id": run_id,
        "revision_key": revision_key,
    }


def render_speaker_exemplars(speaker_id: int) -> None:
    subject = SubjectService.resolve_current_subject(st.session_state)
    run_id = st.session_state.get("run_id")
    if not subject or not run_id:
        st.info("Select a subject to view speaker exemplars.")
        return
    if subject.subject_type != "transcript":
        st.info("Speaker exemplars are available for transcript subjects only.")
        return

    run_dir = RunIndex.get_run_root(subject.scope, run_id, subject_id=subject.subject_id)
    resolved = resolve_effective_config(run_dir=run_dir)
    config = resolved.effective_config.analysis.speaker_exemplars
    if not config.enabled:
        return

    transcript_file = get_transcript_file_for_run(subject.subject_id, run_id)
    if not transcript_file:
        st.info("Transcript file not found for this run.")
        return

    refresh_key = f"speaker_exemplars_refresh_{speaker_id}"
    st.session_state.setdefault(refresh_key, 0)

    col_left, col_right = st.columns([4, 1])
    with col_left:
        st.subheader("Exemplar Lines")
    with col_right:
        if st.button("Recompute exemplars", key=f"recompute_exemplars_{speaker_id}"):
            st.session_state[refresh_key] += 1

    config_payload = json.dumps(asdict(config), sort_keys=True, default=str)
    max_updated, count, max_index = get_transcript_revision_signal(
        transcript_file_id=transcript_file.id
    )
    revision_key = max_updated or f"{count}:{max_index}"

    with st.spinner("Computing speaker exemplars..."):
        results = _compute_cached(
            speaker_id=speaker_id,
            transcript_file_id=transcript_file.id,
            run_id=run_id,
            config_payload=config_payload,
            refresh_nonce=st.session_state[refresh_key],
            revision_key=revision_key,
        )

    meta = results.get("metadata", {})
    st.caption(
        f"segments: {meta.get('deduped_count', 0)} / {meta.get('input_count', 0)} "
        f"· runtime: {meta.get('duration_seconds', 0)}s"
    )
    st.caption(
        f"other sample: {meta.get('other_segments', 'n/a')} "
        f"· methods: {', '.join(meta.get('methods_available', []))}"
    )

    combined = results.get("combined", [])
    per_method = results.get("per_method", {})

    tabs = ["Combined"] + [
        name.replace("_", " ").title() for name in per_method.keys()
    ]
    tab_objs = st.tabs(tabs) if tabs else []
    if not tab_objs:
        st.info("No exemplars available.")
        return

    def render_items(items: list[Dict[str, Any]]) -> None:
        if not items:
            st.info("No exemplars available for this method.")
            return
        for item in items:
            timestamp = _format_time(item.get("start_time"), item.get("end_time"))
            if timestamp:
                st.caption(f"{timestamp}")
            st.write(item.get("text", ""))
            scores = item.get("method_scores") or {}
            if scores:
                st.caption(
                    " · ".join(
                        f"{name}: {score:.2f}" for name, score in scores.items()
                    )
                )
            st.divider()

    with tab_objs[0]:
        render_items(combined)

    for idx, name in enumerate(per_method.keys(), start=1):
        with tab_objs[idx]:
            render_items(per_method.get(name, []))
