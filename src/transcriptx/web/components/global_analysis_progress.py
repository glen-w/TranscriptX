"""
Always-on-top analysis progress chip (top-right).

Shows while a single/group or batch analysis worker is active, including when
the user has navigated away from Run Analysis. Clicking View returns them to
the live progress panel on that page.
"""

from __future__ import annotations

import html
from typing import Any, Literal, Mapping, MutableMapping

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.web.components.progress_panel import SNAPSHOT_KEY
from transcriptx.web.state import PAGE_KEY

_PENDING_LAUNCH_KEY = "run_analysis_pending_launch"
_PENDING_BATCH_KEY = "batch_ops_pending_launch"
_RUN_ANALYSIS_TARGET_KEY = "run_analysis_target"

AnalysisTarget = Literal["Transcript", "Group", "Batch"]

_PHASE_LABELS: dict[str, str] = {
    "validating": "Checking inputs…",
    "running_pipeline": "Running…",
    "finalizing": "Finalizing…",
    "completed": "Completed",
    "failed": "Failed",
    "cancelled": "Cancelled",
}


def is_analysis_operation_active(
    session_state: Mapping[str, Any] | MutableMapping[str, Any] | None = None,
) -> bool:
    """True while a single/group or batch analysis launch is in flight."""
    state = session_state if session_state is not None else st.session_state
    if state.get("analysis_run_in_progress"):
        return True
    pending_batch = state.get(_PENDING_BATCH_KEY)
    return isinstance(pending_batch, dict) and bool(pending_batch.get("execute"))


def resolve_active_analysis_target(
    session_state: Mapping[str, Any] | MutableMapping[str, Any] | None = None,
) -> AnalysisTarget | None:
    """Target mode for the active operation, or None when idle."""
    state = session_state if session_state is not None else st.session_state
    if state.get("analysis_run_in_progress"):
        pending = state.get(_PENDING_LAUNCH_KEY)
        if isinstance(pending, dict):
            target = pending.get("target_type")
            if target in ("Transcript", "Group", "Batch"):
                return target  # type: ignore[return-value]
        return "Transcript"
    pending_batch = state.get(_PENDING_BATCH_KEY)
    if isinstance(pending_batch, dict) and pending_batch.get("execute"):
        return "Batch"
    return None


def sync_run_analysis_target_to_active_operation(
    session_state: MutableMapping[str, Any] | None = None,
) -> AnalysisTarget | None:
    """Force Run Analysis Target to match the ongoing operation (if any)."""
    state = session_state if session_state is not None else st.session_state
    target = resolve_active_analysis_target(state)
    if target is not None:
        state[_RUN_ANALYSIS_TARGET_KEY] = target
    return target


def _snapshot_summary(snapshot: Mapping[str, Any] | None) -> tuple[str, float, str]:
    """Return (title, pct 0-100, detail line) for the chip."""
    if not isinstance(snapshot, Mapping):
        return "Analysis running…", 0.0, ""
    phase = str(snapshot.get("phase") or "running_pipeline")
    status = str(snapshot.get("status") or "running")
    title = _PHASE_LABELS.get(phase, phase.replace("_", " ").title())
    if status == "completed":
        title = "Completed"
    elif status == "failed":
        title = "Failed"
    elif status == "cancelled":
        title = "Cancelled"
    try:
        pct = float(snapshot.get("pct") or 0.0)
    except (TypeError, ValueError):
        pct = 0.0
    pct = max(0.0, min(100.0, pct))
    detail_parts: list[str] = []
    item = str(snapshot.get("current_item") or "").strip()
    module = str(snapshot.get("current_module") or "").strip()
    if item:
        detail_parts.append(item)
    if module:
        detail_parts.append(module)
    completed = snapshot.get("completed", 0) or 0
    skipped = snapshot.get("skipped", 0) or 0
    failed = snapshot.get("failed", 0) or 0
    total = snapshot.get("total", 0) or 0
    done = int(completed) + int(skipped) + int(failed)
    if int(total) > 0:
        detail_parts.append(f"{done}/{int(total)}")
    return title, pct, " · ".join(detail_parts)


def _render_chip_html(*, title: str, pct: float, detail: str, target: str) -> str:
    safe_title = html.escape(title)
    safe_detail = html.escape(detail) if detail else ""
    safe_target = html.escape(target)
    width = f"{pct:.1f}"
    detail_html = (
        f'<div class="tx-global-run-progress__detail">{safe_detail}</div>'
        if safe_detail
        else ""
    )
    return (
        '<div class="tx-global-run-progress" role="status" '
        'aria-live="polite">'
        '<div class="tx-global-run-progress__row">'
        f'<span class="tx-global-run-progress__title">{safe_title}</span>'
        f'<span class="tx-global-run-progress__meta">{safe_target}</span>'
        "</div>"
        f"{detail_html}"
        '<div class="tx-global-run-progress__track" aria-hidden="true">'
        f'<div class="tx-global-run-progress__fill" style="width:{width}%"></div>'
        "</div>"
        f'<div class="tx-global-run-progress__pct">{width}%</div>'
        "</div>"
    )


@st.fragment(run_every=0.5)
def _global_analysis_progress_fragment() -> None:
    """Poll snapshot while a run is active (works off the Run Analysis page)."""
    if not is_analysis_operation_active():
        return
    # Page owns the full panel; skip the floating chip there.
    if st.session_state.get(PAGE_KEY) == "Run Analysis":
        return

    target = resolve_active_analysis_target() or "Transcript"
    snapshot = st.session_state.get(SNAPSHOT_KEY)
    title, pct, detail = _snapshot_summary(
        snapshot if isinstance(snapshot, Mapping) else None
    )

    st.markdown(
        '<div class="tx-global-run-progress-flag" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    cols = st.columns([5, 1.2], gap="small")
    with cols[0]:
        st.markdown(
            _render_chip_html(title=title, pct=pct, detail=detail, target=target),
            unsafe_allow_html=True,
        )
    with cols[1]:
        if st.button(
            "View",
            key="tx_global_analysis_view",
            icon=ic.VISIBILITY,
            help="Open Run Analysis to see live progress and controls.",
            width="stretch",
        ):
            st.session_state[PAGE_KEY] = "Run Analysis"
            st.session_state[_RUN_ANALYSIS_TARGET_KEY] = target
            st.rerun()


def render_global_analysis_progress() -> None:
    """Shell entry: mount the floating chip when an analysis operation is active."""
    if not is_analysis_operation_active():
        return
    if st.session_state.get(PAGE_KEY) == "Run Analysis":
        return
    _global_analysis_progress_fragment()
