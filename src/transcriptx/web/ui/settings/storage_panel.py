"""Settings storage roots + bulk analysis-run cleanup UI."""

from __future__ import annotations

import uuid
from collections import defaultdict

import streamlit as st

from transcriptx.app.controllers.settings_controller import SettingsController
from transcriptx.web.services.run_cleanup import (
    CONFIRM_DELETE_ALL,
    CONFIRM_DELETE_OLD,
    CleanupAuthorization,
    CleanupMode,
    CleanupResult,
    CleanupStatus,
    RunCleanupService,
)
from transcriptx.web.services.run_cleanup.session_clear import (
    clear_session_selections_for_removed_runs,
)

_SESSION_ID_KEY = "_cleanup_ui_session_id"
_HANDLE_KEY = "_cleanup_plan_handle"
_PLAN_ID_KEY = "_cleanup_plan_id"
_MODE_KEY = "_cleanup_mode"
_ACK_KEY = "_cleanup_ack"
_PHRASE_KEY = "_cleanup_phrase"
_PREVIEW_KEY = "_cleanup_preview"
_RESULT_KEY = "_cleanup_last_result"


def _ui_session_id() -> str:
    if _SESSION_ID_KEY not in st.session_state:
        st.session_state[_SESSION_ID_KEY] = uuid.uuid4().hex
    return str(st.session_state[_SESSION_ID_KEY])


def _reset_confirmation_state() -> None:
    # Pop widget keys — never assign after the checkbox/input are instantiated.
    st.session_state.pop(_ACK_KEY, None)
    st.session_state.pop(_PHRASE_KEY, None)


def _clear_preview_state() -> None:
    for key in (_HANDLE_KEY, _PLAN_ID_KEY, _MODE_KEY, _PREVIEW_KEY):
        st.session_state.pop(key, None)
    _reset_confirmation_state()


def _format_bytes(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{n} B"


def _render_cleanup_result(result: CleanupResult) -> None:
    """Surface status, operation id, errors/warnings, and per-target detail."""
    op = result.operation_id or "(none)"
    if result.status is CleanupStatus.SUCCESS:
        st.success(
            f"Cleanup complete (operation {op}). "
            f"Removed {result.visible_removed_count} run(s); "
            f"physically deleted {result.physically_deleted_count}."
        )
    elif result.status is CleanupStatus.PARTIAL:
        parts = [
            f"Partial cleanup (operation {op}; "
            f"{result.visible_removed_count} removed)."
        ]
        if result.errors:
            parts.append("; ".join(result.errors[:5]))
        if result.warnings:
            parts.append("; ".join(result.warnings[:5]))
        st.warning(" ".join(parts))
    elif result.status is CleanupStatus.STALE_PLAN:
        st.error(
            f"Plan is stale (operation {op}) — generate a new preview and confirm again."
        )
    elif result.status is CleanupStatus.ALREADY_EXECUTED:
        st.info(f"This cleanup was already executed (operation {op}).")
    elif result.status is CleanupStatus.NOOP:
        st.info(f"Nothing to delete (operation {op}).")
    else:
        st.error(
            f"{result.status.value} (operation {op}): "
            + ("; ".join(result.errors) or "Cleanup blocked")
        )

    with st.expander("Per-target results"):
        if not result.targets:
            st.caption("No per-target results.")
        for t in result.targets:
            st.text(
                f"{t.subject_type.value}/{t.subject_id}/{t.run_id}: "
                f"{t.status.value} {t.message}"
            )


def _render_pending_staging_section() -> None:
    st.subheader("Pending staging recovery")
    st.caption(
        "Interrupted cleanup operations that still have journaled staging state. "
        "Retry finishes physical deletion for recoverable remnants."
    )
    svc = RunCleanupService()
    pending = svc.list_pending_staging()
    if not pending:
        st.caption("No pending staging operations.")
        return

    by_op: dict[str, list[dict]] = defaultdict(list)
    for row in pending:
        by_op[str(row.get("operation_id") or "")].append(row)

    for operation_id, rows in sorted(by_op.items()):
        with st.expander(
            f"Operation {operation_id} ({len(rows)} target(s))", expanded=False
        ):
            st.text(
                f"plan_id={rows[0].get('plan_id')} mode={rows[0].get('mode')} "
                f"status={rows[0].get('operation_status')}"
            )
            for row in rows:
                st.text(
                    f"{row.get('subject_type')}/{row.get('subject_id')}/{row.get('run_id')}: "
                    f"state={row.get('state')} "
                    f"path={row.get('staging_path') or row.get('canonical_path')}"
                )
            if st.button(
                f"Retry recovery ({operation_id})",
                key=f"_cleanup_retry_{operation_id}",
            ):
                result = svc.retry_interrupted_staging(operation_id)
                clear_session_selections_for_removed_runs(
                    st.session_state, result.targets
                )
                _render_cleanup_result(result)


def _render_cleanup_section() -> None:
    st.subheader("Analysis run cleanup")
    st.caption(
        "Deletes reconstructable analysis run directories under the outputs roots only. "
        "Transcripts, recordings, corrections, speaker maps, import metadata, group "
        "definitions, configuration, and the slug index are never touched. "
        "This is irreversible and may complete only partially. "
        "Disk sizes are estimates (sum of regular-file sizes)."
    )
    st.warning(
        "Files manually added inside a selected run directory are deleted with that run."
    )

    # Execute stores the result and reruns so confirmation widget keys can be
    # cleared before the checkbox/input are instantiated on the next run.
    pending_result = st.session_state.pop(_RESULT_KEY, None)
    if pending_result is not None:
        _reset_confirmation_state()
        _render_cleanup_result(pending_result)

    mode_label = st.radio(
        "Cleanup action",
        options=["Delete all runs", "Delete old runs"],
        horizontal=True,
        key="_cleanup_mode_radio",
        help=(
            "Delete all: remove every eligible analysis run. "
            "Delete old: keep the newest run per transcript and per group."
        ),
    )
    mode = (
        CleanupMode.DELETE_ALL
        if mode_label == "Delete all runs"
        else CleanupMode.DELETE_OLD
    )
    confirm_phrase = (
        CONFIRM_DELETE_ALL if mode is CleanupMode.DELETE_ALL else CONFIRM_DELETE_OLD
    )

    # Reset confirmation when mode changes relative to stored preview
    stored_mode = st.session_state.get(_MODE_KEY)
    if stored_mode is not None and stored_mode != mode.value:
        _clear_preview_state()

    if st.button("Generate preview", key="_cleanup_preview_btn"):
        svc = RunCleanupService()
        handle, preview = svc.preview_cleanup(mode, _ui_session_id())
        st.session_state[_HANDLE_KEY] = handle
        st.session_state[_PLAN_ID_KEY] = preview.plan_id
        st.session_state[_MODE_KEY] = mode.value
        st.session_state[_PREVIEW_KEY] = preview
        _reset_confirmation_state()
        st.rerun()

    preview = st.session_state.get(_PREVIEW_KEY)
    if preview is None:
        st.info("Generate a preview to see what would be deleted.")
        return

    if preview.blocking_errors:
        for err in preview.blocking_errors:
            st.error(err)
    for warn in preview.warnings:
        st.warning(warn)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Subjects", preview.transcript_subjects + preview.group_subjects)
    c2.metric("Runs to delete", preview.run_count)
    c3.metric("Files (est.)", preview.file_count)
    c4.metric("Size (est.)", _format_bytes(preview.size_estimate_bytes))

    st.markdown("**Runs to delete**")
    if preview.candidates:
        st.dataframe(
            [
                {
                    "subject_type": row.get("subject_type"),
                    "subject": row.get("subject_id"),
                    "run_id": row.get("run_id"),
                    "path": row.get("root_relative_path"),
                    "files": row.get("file_count"),
                    "size_est": row.get("size_estimate_bytes"),
                }
                for row in preview.candidates
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("No deletion candidates.")

    if preview.retained:
        st.markdown("**Retained newest runs**")
        st.dataframe(
            [
                {
                    "subject_type": row.get("subject_type"),
                    "subject": row.get("subject_id"),
                    "run_id": row.get("run_id"),
                    "path": row.get("root_relative_path"),
                }
                for row in preview.retained
            ],
            width="stretch",
            hide_index=True,
        )

    if preview.exclusions:
        with st.expander(f"Excluded / unknown entries ({len(preview.exclusions)})"):
            for ex in preview.exclusions:
                st.text(
                    f"{ex.get('classification')}: {ex.get('path_relative')} — {ex.get('reason')}"
                )

    if not preview.can_execute:
        st.error("This plan cannot be executed (see errors above).")
        return

    ack = st.checkbox(
        "I understand this permanently deletes analysis outputs",
        key=_ACK_KEY,
    )
    phrase_ok = False
    if ack:
        typed = st.text_input(
            f"Type {confirm_phrase} to confirm",
            key=_PHRASE_KEY,
            help="Exact match required (case-sensitive, no trimming).",
        )
        # Service validates untrimmed; UI must not strip before submit.
        phrase_ok = typed == confirm_phrase
        if typed and not phrase_ok:
            st.caption("Phrase does not match exactly.")

    execute_disabled = not (ack and phrase_ok)
    if st.button(
        "Execute cleanup",
        type="primary",
        disabled=execute_disabled,
        key="_cleanup_execute_btn",
    ):
        handle = st.session_state.get(_HANDLE_KEY)
        plan_id = st.session_state.get(_PLAN_ID_KEY)
        if not handle or not plan_id:
            st.error("Preview handle missing; generate a new preview.")
            return
        # Read raw session value without trimming
        typed_phrase = st.session_state.get(_PHRASE_KEY, "")
        auth = CleanupAuthorization(
            acknowledged=bool(st.session_state.get(_ACK_KEY)),
            phrase=typed_phrase if isinstance(typed_phrase, str) else "",
            mode=mode,
            plan_id=str(plan_id),
        )
        svc = RunCleanupService()
        result = svc.execute_cleanup(handle, auth, _ui_session_id())
        clear_session_selections_for_removed_runs(st.session_state, result.targets)
        st.session_state[_RESULT_KEY] = result
        # Clear non-widget keys only; ack/phrase are popped on the next run.
        for key in (_HANDLE_KEY, _PLAN_ID_KEY, _MODE_KEY, _PREVIEW_KEY):
            st.session_state.pop(key, None)
        st.rerun()


def render_storage_panel() -> None:
    """Show configured storage root paths and cleanup controls."""
    st.subheader("Storage roots")
    ctrl = SettingsController()
    roots = ctrl.get_storage_roots()
    for name, path in roots.items():
        st.text(f"{name}: {path}")

    st.divider()
    _render_cleanup_section()
    st.divider()
    _render_pending_staging_section()
