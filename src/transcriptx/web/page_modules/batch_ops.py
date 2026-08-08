"""
Batch analysis panel (embedded on Run Analysis).

Selection widgets run in ``@st.fragment`` so multiselect chip toggles do not rerun
the full app (sidebar + page chrome).

Live progress uses the same ``StreamlitProgressCallback`` + panel as single/group
runs (bar + recent logs), not a blocking spinner. Launch is three-phase so a
short ``form_cleared`` rerun drops prior selection widgets before execute.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import streamlit as st

from transcriptx.app.controllers.batch_controller import BatchController
from transcriptx.app.models.errors import ValidationError, WorkflowExecutionError
from transcriptx.app.models.requests import BatchAnalysisRequest
from transcriptx.app.models.results import BatchAnalysisResult
from transcriptx.app.progress import make_initial_snapshot
from transcriptx.web.cache_helpers import (
    cached_get_module_info_list,
    clear_run_listing_caches,
    get_cached_list_transcript_picker_options,
)
from transcriptx.web.components.analysis_preset_controls import (
    apply_custom_qa_to_plan,
    render_analysis_preset_selector,
    render_effective_module_summary,
)
from transcriptx.web.components.llm_custom_qa_picker import render_custom_qa_picker
from transcriptx.web.components.llm_model_selector import render_compact_llm_setup
from transcriptx.web.components.progress_panel import (
    SNAPSHOT_KEY,
    StreamlitProgressCallback,
    render_progress_panel,
)
from transcriptx.web.components.recent_run_row import render_recent_run_row
from transcriptx.web.sidebar_options import _slug_display_labels_from_index

_BATCH_RESULT_KEY = "batch_ops_last_result"
_PENDING_BATCH_KEY = "batch_ops_pending_launch"


def _sanitize_batch_widget_state(option_keys: list[str]) -> None:
    """Drop stale multiselect values before keyed widgets bind."""
    allowed_paths = set(option_keys)
    raw_transcripts = st.session_state.get("batch_transcripts")
    if isinstance(raw_transcripts, list):
        cleaned = [p for p in raw_transcripts if p in allowed_paths]
        if cleaned != raw_transcripts:
            st.session_state["batch_transcripts"] = cleaned
    elif raw_transcripts is not None:
        st.session_state["batch_transcripts"] = []


@st.fragment
def _batch_ops_selection_fragment(
    option_keys: list[str],
    transcript_options: Mapping[str, str],
) -> None:
    """High-churn transcript multiselect only."""

    def _format_option(path_key: str) -> str:
        return transcript_options.get(path_key, path_key)

    st.multiselect(
        "Select transcripts to process",
        options=option_keys,
        default=[],
        format_func=_format_option,
        key="batch_transcripts",
        help="Choose one or more transcripts from the library.",
    )


def _render_batch_result(result) -> None:
    """Show batch summary banner plus recent-run-style rows for successful runs."""
    if result.success:
        st.success(
            result.message or f"Processed {result.transcript_count} transcript(s)."
        )
    else:
        st.error("Batch analysis completed with errors.")
        for e in result.errors:
            st.error(e)
        if result.message and result.runs:
            st.info(result.message)

    runs = getattr(result, "runs", None) or []
    if not runs:
        return

    st.markdown("#### Processed runs")
    slug_labels = _slug_display_labels_from_index()
    for idx, run in enumerate(runs):
        render_recent_run_row(
            run,
            row_index=idx,
            slug_labels=slug_labels,
            key_prefix="batch_run",
            tip_control_prefix="tx-batch-run-tip",
        )


def _finalize_batch_snapshot(
    *,
    success: bool,
    message: str,
    error: str | None = None,
) -> None:
    """Align the shared progress snapshot with overall batch outcome."""
    snap = st.session_state.get(SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        return
    if success:
        snap["status"] = "completed"
        snap["phase"] = "completed"
        snap["pct"] = 100.0
        snap["latest_event"] = message or "Batch completed"
        snap["error"] = None
    else:
        snap["status"] = "failed"
        snap["phase"] = "failed"
        snap["latest_event"] = message or "Batch failed"
        if error:
            snap["error"] = error


def _execute_pending_batch(
    pending: dict,
    *,
    progress: StreamlitProgressCallback,
) -> None:
    """Run stored batch request; progress panel is the run affordance."""
    request = pending["request"]
    st.session_state.pop(_BATCH_RESULT_KEY, None)
    try:
        result = BatchController().run_batch_analysis(request, progress=progress)
        st.session_state[_BATCH_RESULT_KEY] = result
        _finalize_batch_snapshot(
            success=bool(result.success),
            message=str(result.message or ""),
            error=(
                "; ".join(result.errors)
                if isinstance(result, BatchAnalysisResult) and result.errors
                else None
            ),
        )
    except (ValidationError, WorkflowExecutionError) as exc:
        msg = str(exc) or "Batch analysis failed."
        st.error(msg)
        st.session_state["_batch_ops_flash_error"] = msg
        _finalize_batch_snapshot(success=False, message=msg, error=msg)
    except Exception as exc:  # noqa: BLE001 — keep merged page responsive
        msg = f"Batch analysis failed: {exc}"
        st.error(msg)
        st.session_state["_batch_ops_flash_error"] = msg
        _finalize_batch_snapshot(success=False, message=msg, error=msg)
    finally:
        clear_run_listing_caches()
        st.session_state.pop(_PENDING_BATCH_KEY, None)
        progress.refresh_panel()
    st.rerun()


def render_batch_analysis_panel() -> None:
    """Render batch selection, launch, and results (no page chrome)."""
    picker_options = get_cached_list_transcript_picker_options()

    if not picker_options:
        st.info("No transcripts found. Add transcript JSON files first.")
        return

    transcript_options = {opt.path: opt.label for opt in picker_options}
    option_keys = list(transcript_options.keys())

    modules_info = cached_get_module_info_list()
    module_names = [m["name"] for m in modules_info]

    _sanitize_batch_widget_state(option_keys)

    pending = st.session_state.get(_PENDING_BATCH_KEY)
    if isinstance(pending, dict) and pending.get("execute"):
        # Three-phase launch so Streamlit can drop the prior form widgets:
        # 1) click stores pending + rerun
        # 2) paint progress only + form_cleared + rerun (ends script → clears form)
        # 3) paint progress + execute (blocking; form stays gone)
        progress_slot = st.empty()
        snapshot = st.session_state.get(SNAPSHOT_KEY)
        if snapshot is not None:
            with progress_slot.container():
                render_progress_panel(snapshot)
        else:
            with progress_slot.container():
                st.info("Batch analysis is running…")
        if not pending.get("form_cleared"):
            pending["form_cleared"] = True
            st.session_state[_PENDING_BATCH_KEY] = pending
            st.rerun()
            return
        if not pending.get("started"):
            pending["started"] = True
            st.session_state[_PENDING_BATCH_KEY] = pending
            modules = list(
                getattr(pending.get("request"), "selected_modules", None) or []
            )
            if SNAPSHOT_KEY not in st.session_state:
                st.session_state[SNAPSHOT_KEY] = make_initial_snapshot(
                    len(modules) or 1
                )
            progress = StreamlitProgressCallback(render_slot=progress_slot)
            progress.refresh_panel()
            _execute_pending_batch(pending, progress=progress)
        return

    flash_error = st.session_state.pop("_batch_ops_flash_error", None)
    if flash_error:
        st.error(flash_error)

    _batch_ops_selection_fragment(
        option_keys,
        transcript_options,
    )

    selected_keys = list(st.session_state.get("batch_transcripts") or [])
    selected_paths = [Path(p) for p in selected_keys] if selected_keys else []
    transcript_targets = tuple(str(p) for p in selected_paths)

    resolved = render_analysis_preset_selector(
        key_prefix="batch",
        target="batch",
        transcript_targets=transcript_targets or None,
        available_modules=module_names,
    )

    qa_request_questions, qa_effective, custom_qa_execution = render_custom_qa_picker(
        key_prefix="batch_qa",
        always_show=True,
    )
    plan = apply_custom_qa_to_plan(resolved, custom_qa_execution=custom_qa_execution)
    render_effective_module_summary(
        plan,
        preset=resolved.preset,
        key_prefix="batch",
        qa_key_prefix="batch_qa",
    )
    selected_modules = list(plan.module_ids)

    from transcriptx.core.analysis.llm_custom_qa.questions_binding import (
        bind_custom_qa_questions,
        reset_custom_qa_questions,
    )

    _qa_ui_token = None
    if qa_effective is not None:
        _qa_ui_token = bind_custom_qa_questions(qa_effective)
    try:
        llm_selection, llm_gates, _model_label = render_compact_llm_setup(
            key_prefix="batch_llm",
            selected_modules=selected_modules,
            include_group=False,
        )
    finally:
        if _qa_ui_token is not None:
            reset_custom_qa_questions(_qa_ui_token)

    can_launch = bool(selected_paths) and bool(selected_modules) and not llm_gates
    if st.button(
        "Run Batch Analysis",
        type="primary",
        key="batch_run",
        disabled=not can_launch,
    ):
        if not selected_paths:
            st.warning("Select at least one transcript to process.")
        elif not selected_modules:
            st.warning("Select at least one module.")
        else:
            st.session_state.pop(_BATCH_RESULT_KEY, None)
            request = BatchAnalysisRequest(
                transcript_paths=selected_paths,
                analysis_mode=resolved.mode,
                selected_modules=selected_modules,
                analysis_preset=resolved.preset,
                llm_model_selection=llm_selection,
                llm_custom_qa_questions=qa_request_questions,
            )
            st.session_state[SNAPSHOT_KEY] = make_initial_snapshot(
                len(selected_modules)
            )
            st.session_state[_PENDING_BATCH_KEY] = {
                "request": request,
                "execute": True,
                "form_cleared": False,
                "started": False,
            }
            st.rerun()

    last_snapshot = st.session_state.get(SNAPSHOT_KEY)
    if last_snapshot and last_snapshot.get("status") in ("completed", "failed"):
        with st.expander("Last run progress", expanded=False):
            render_progress_panel(last_snapshot)

    last_result = st.session_state.get(_BATCH_RESULT_KEY)
    if last_result is not None:
        _render_batch_result(last_result)
