"""Settings → Corrections panel for library-wide candidate generation."""

from __future__ import annotations

import streamlit as st

from transcriptx.services.corrections_studio.bulk_generation import (
    CONFIRM_REGENERATE_ALL,
    BulkGenerationMode,
    BulkGenerationResult,
    BulkTargetStatus,
)
from transcriptx.services.corrections_studio.controller import (
    CorrectionsStudioController,
)

_MODE_KEY = "_corrections_bulk_mode"
_PREVIEW_KEY = "_corrections_bulk_preview"
_RESULT_KEY = "_corrections_bulk_last_result"
_ACK_KEY = "_corrections_bulk_ack"
_PHRASE_KEY = "_corrections_bulk_phrase"


def _reset_confirmation_state() -> None:
    st.session_state.pop(_ACK_KEY, None)
    st.session_state.pop(_PHRASE_KEY, None)


def _clear_preview_state() -> None:
    st.session_state.pop(_PREVIEW_KEY, None)
    st.session_state.pop(_MODE_KEY, None)
    _reset_confirmation_state()


def _render_bulk_result(result: BulkGenerationResult) -> None:
    parts = [
        f"Generated {result.generated_count}",
        f"skipped {result.skipped_count}",
        f"aborted {result.aborted_count}",
        f"errors {result.error_count}",
    ]
    summary = "; ".join(parts) + "."
    if result.error_count or result.aborted_count:
        st.warning(f"Bulk candidate run finished with issues. {summary}")
    elif result.generated_count == 0 and result.skipped_count > 0:
        st.info(f"Nothing new to generate. {summary}")
    else:
        st.success(f"Bulk candidate run complete. {summary}")

    with st.expander("Per-transcript results", expanded=bool(result.error_count)):
        if not result.targets:
            st.caption("No transcripts processed.")
            return
        for target in result.targets:
            label = target.base_name or target.path
            detail = f"{label}: {target.status.value}"
            if target.candidate_count:
                detail += f" ({target.candidate_count} candidates)"
            if target.message:
                detail += f" — {target.message}"
            if target.status is BulkTargetStatus.ERROR:
                st.error(detail)
            elif target.status is BulkTargetStatus.ABORTED:
                st.warning(detail)
            else:
                st.text(detail)


def render_corrections_panel() -> None:
    """Bulk generate / regenerate correction candidates for all transcripts."""
    st.subheader("Correction candidates")
    st.caption(
        "Generate or regenerate Corrections Studio candidates for every managed "
        "transcript. Generate missing skips sessions that already have candidates; "
        "regenerate always recomputes (reviews are migrated where possible). "
        "Use regenerate after changing correction config, speaker maps, or memory rules."
    )

    pending_result = st.session_state.pop(_RESULT_KEY, None)
    if pending_result is not None:
        _reset_confirmation_state()
        _render_bulk_result(pending_result)

    mode_label = st.radio(
        "Bulk action",
        options=["Generate missing", "Regenerate all"],
        horizontal=True,
        key="_corrections_bulk_mode_radio",
        help=(
            "Generate missing: create candidates only where none exist. "
            "Regenerate all: re-run detectors (and optional LLM discovery) for every transcript."
        ),
    )
    mode = (
        BulkGenerationMode.REGENERATE_ALL
        if mode_label == "Regenerate all"
        else BulkGenerationMode.GENERATE_MISSING
    )

    stored_mode = st.session_state.get(_MODE_KEY)
    if stored_mode is not None and stored_mode != mode.value:
        _clear_preview_state()

    if st.button("Refresh inventory", key="_corrections_bulk_preview_btn"):
        ctrl = CorrectionsStudioController()
        preview = ctrl.preview_bulk_candidate_generation(mode)
        st.session_state[_PREVIEW_KEY] = preview
        st.session_state[_MODE_KEY] = mode.value
        _reset_confirmation_state()
        st.rerun()

    preview = st.session_state.get(_PREVIEW_KEY)
    if preview is None or st.session_state.get(_MODE_KEY) != mode.value:
        st.info("Refresh inventory to see how many transcripts need candidates.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Transcripts", preview.transcript_count)
    c2.metric("With candidates", preview.with_candidates)
    c3.metric("Without candidates", preview.without_candidates)
    c4.metric("Actionable", preview.actionable_count)

    if preview.transcript_count == 0:
        st.caption("No managed transcripts found.")
        return

    with st.expander("Transcript inventory", expanded=False):
        st.dataframe(
            [
                {
                    "name": row.base_name,
                    "candidates": row.candidate_count,
                    "status": "has candidates" if row.has_candidates else "missing",
                    "path": row.path,
                }
                for row in preview.targets
            ],
            width="stretch",
            hide_index=True,
        )

    if preview.actionable_count == 0:
        st.info("Nothing to do for this action.")
        return

    execute_disabled = False
    if mode is BulkGenerationMode.REGENERATE_ALL:
        st.warning(
            "Regenerate recomputes candidates for every transcript and may change "
            "pending review state even when prior decisions are migrated."
        )
        ack = st.checkbox(
            "I understand this regenerates candidates for all transcripts",
            key=_ACK_KEY,
            help="Required acknowledgment before regenerate-all can run.",
        )
        phrase_ok = False
        if ack:
            typed = st.text_input(
                f"Type {CONFIRM_REGENERATE_ALL} to confirm",
                key=_PHRASE_KEY,
                help="Exact match required (case-sensitive, no trimming).",
            )
            phrase_ok = typed == CONFIRM_REGENERATE_ALL
            if typed and not phrase_ok:
                st.caption("Phrase does not match exactly.")
        execute_disabled = not (ack and phrase_ok)

    button_label = (
        "Regenerate all candidates"
        if mode is BulkGenerationMode.REGENERATE_ALL
        else "Generate missing candidates"
    )
    if st.button(
        button_label,
        type="primary",
        disabled=execute_disabled,
        key="_corrections_bulk_execute_btn",
    ):
        ctrl = CorrectionsStudioController()
        progress = st.progress(0.0, text="Starting…")
        status = st.empty()

        def _on_progress(index: int, total: int, name: str) -> None:
            frac = index / total if total else 1.0
            progress.progress(min(frac, 1.0), text=f"{index}/{total}: {name}")
            status.caption(f"Processing {name}")

        result = ctrl.run_bulk_candidate_generation(
            mode, progress_callback=_on_progress
        )
        progress.progress(1.0, text="Done")
        st.session_state[_RESULT_KEY] = result
        for key in (_PREVIEW_KEY, _MODE_KEY):
            st.session_state.pop(key, None)
        st.rerun()
