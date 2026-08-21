"""
Batch analysis panel (embedded on Run Analysis).

Selection widgets run in ``@st.fragment`` so multiselect chip toggles do not rerun
the full app (sidebar + page chrome).

Live progress uses the same ``StreamlitProgressCallback`` + panel as single/group
runs (bar + recent logs), not a blocking spinner. Launch is three-phase so a
short ``form_cleared`` rerun drops prior selection widgets before execute.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.app.controllers.batch_controller import BatchController
from transcriptx.app.models.errors import ValidationError, WorkflowExecutionError
from transcriptx.app.models.requests import BatchAnalysisRequest
from transcriptx.app.progress import make_initial_snapshot
from transcriptx.core.pipeline.run_control import (
    PipelineRunControl,
    bind_run_control,
    reset_run_control,
)
from transcriptx.web.cache_helpers import (
    cached_get_module_info_list,
    clear_run_listing_caches,
    get_cached_list_transcript_picker_options,
)
from transcriptx.web.components.info_tooltip import widget_help
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
_BATCH_CONTROL_KEY = "batch_ops_run_control"
_BATCH_WORKER_HOLDER_KEY = "batch_ops_worker_holder"


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
        help=widget_help("Choose one or more transcripts from the library."),
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
    cancelled: bool = False,
) -> None:
    """Align the shared progress snapshot with overall batch outcome."""
    snap = st.session_state.get(SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        return
    if cancelled:
        snap["status"] = "cancelled"
        snap["phase"] = "cancelled"
        snap["latest_event"] = message or "Batch cancelled"
        snap["error"] = error
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


def _clear_batch_in_progress_state() -> None:
    st.session_state.pop(_PENDING_BATCH_KEY, None)
    st.session_state.pop(_BATCH_CONTROL_KEY, None)
    st.session_state.pop(_BATCH_WORKER_HOLDER_KEY, None)


def _start_pending_batch_worker(pending: dict) -> None:
    request = pending["request"]
    snapshot = st.session_state.get(SNAPSHOT_KEY)
    if not isinstance(snapshot, dict):
        modules = list(getattr(request, "selected_modules", None) or [])
        snapshot = make_initial_snapshot(len(modules) or 1)
        st.session_state[SNAPSHOT_KEY] = snapshot
    progress = StreamlitProgressCallback(snapshot=snapshot)
    control = PipelineRunControl()
    holder: dict[str, Any] = {"done": False, "result": None, "error": None}
    st.session_state.pop(_BATCH_RESULT_KEY, None)
    st.session_state[_BATCH_CONTROL_KEY] = control
    st.session_state[_BATCH_WORKER_HOLDER_KEY] = holder

    def _worker() -> None:
        token = bind_run_control(control)
        try:
            holder["result"] = BatchController().run_batch_analysis(
                request, progress=progress
            )
        except Exception as exc:  # noqa: BLE001 — surface on the UI thread
            holder["error"] = exc
        finally:
            reset_run_control(token)
            holder["done"] = True

    threading.Thread(target=_worker, name="tx-batch-analysis", daemon=True).start()


def _finish_pending_batch(holder: dict[str, Any]) -> None:
    error = holder.get("error")
    result = holder.get("result")
    _clear_batch_in_progress_state()
    clear_run_listing_caches()
    if error is not None:
        if isinstance(error, (ValidationError, WorkflowExecutionError)):
            msg = str(error) or "Batch analysis failed."
        else:
            msg = f"Batch analysis failed: {error}"
        st.error(msg)
        st.session_state["_batch_ops_flash_error"] = msg
        _finalize_batch_snapshot(success=False, message=msg, error=msg)
        st.rerun()
        return
    if result is not None:
        st.session_state[_BATCH_RESULT_KEY] = result
        errors = list(getattr(result, "errors", None) or [])
        cancelled = any("cancel" in str(e).lower() for e in errors)
        _finalize_batch_snapshot(
            success=bool(getattr(result, "success", False)),
            message=str(getattr(result, "message", "") or ""),
            error="; ".join(str(e) for e in errors) if errors else None,
            cancelled=cancelled,
        )
    st.rerun()


def _render_batch_in_progress_controls() -> None:
    snapshot = st.session_state.get(SNAPSHOT_KEY)
    if snapshot is not None:
        render_progress_panel(snapshot)
    else:
        st.info("Batch analysis is running…")

    control = st.session_state.get(_BATCH_CONTROL_KEY)
    cancelling = isinstance(control, PipelineRunControl) and control.is_cancelled()
    skipping = (
        isinstance(control, PipelineRunControl)
        and control.skip_event.is_set()
        and not cancelling
    )
    cols = st.columns([1.5, 1.6, 3])
    with cols[0]:
        if st.button(
            "Skip module",
            key="batch_ops_skip",
            icon=ic.SKIP,
            disabled=cancelling or skipping,
            width="stretch",
            help="Abandon the module that is running and continue with the rest.",
        ):
            if isinstance(control, PipelineRunControl):
                control.request_skip()
            if isinstance(snapshot, dict):
                snapshot["latest_event"] = "Skipping current module…"
            st.rerun()
    with cols[1]:
        if st.button(
            "Cancel analysis",
            key="batch_ops_cancel",
            icon=ic.STOP,
            disabled=cancelling,
            width="stretch",
            help="Stop this batch. The current module is abandoned; later work is not started.",
        ):
            if isinstance(control, PipelineRunControl):
                control.request_cancel()
            if isinstance(snapshot, dict):
                snapshot["latest_event"] = (
                    "Cancelling — waiting for the current module to stop…"
                )
            st.rerun()
    if cancelling:
        st.caption("Cancelling… remaining transcripts will not start.")
    elif skipping:
        st.caption("Skipping current module…")


def _poll_batch_in_progress() -> None:
    _render_batch_in_progress_controls()
    holder = st.session_state.get(_BATCH_WORKER_HOLDER_KEY)
    if isinstance(holder, dict) and holder.get("done"):
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
        # 3) start a background worker and poll so Skip / Cancel stay clickable
        if not pending.get("form_cleared"):
            snapshot = st.session_state.get(SNAPSHOT_KEY)
            if snapshot is not None:
                render_progress_panel(snapshot)
            else:
                st.info("Batch analysis is running…")
            pending["form_cleared"] = True
            st.session_state[_PENDING_BATCH_KEY] = pending
            st.rerun()
            return
        if not pending.get("started"):
            pending["started"] = True
            st.session_state[_PENDING_BATCH_KEY] = pending
            if SNAPSHOT_KEY not in st.session_state:
                modules = list(
                    getattr(pending.get("request"), "selected_modules", None) or []
                )
                st.session_state[SNAPSHOT_KEY] = make_initial_snapshot(
                    len(modules) or 1
                )
            _start_pending_batch_worker(pending)
        holder = st.session_state.get(_BATCH_WORKER_HOLDER_KEY)
        if isinstance(holder, dict) and holder.get("done"):
            _finish_pending_batch(holder)
            return
        poll = st.fragment(run_every=0.5)(_poll_batch_in_progress)
        poll()
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
        icon=ic.RUN,
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
    if last_snapshot and last_snapshot.get("status") in (
        "completed",
        "failed",
        "cancelled",
    ):
        with st.expander("Last run progress", expanded=False):
            render_progress_panel(last_snapshot)

    last_result = st.session_state.get(_BATCH_RESULT_KEY)
    if last_result is not None:
        _render_batch_result(last_result)
