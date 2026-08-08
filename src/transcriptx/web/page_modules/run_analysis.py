"""
Run Analysis page - configure and execute single-transcript or group analysis.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from transcriptx.app.controllers.analysis_controller import AnalysisController
from transcriptx.app.models.requests import AnalysisRequest, GroupAnalysisRequest
from transcriptx.app.models.results import RunSummary
from transcriptx.app.output_capture import capture_output
from transcriptx.app.progress import make_initial_snapshot
from transcriptx.core.domain.group import Group
from transcriptx.core.utils.config import get_config
from transcriptx.web.action_menus.context import ActionContext, build_canonical_identity
from transcriptx.web.action_menus.ids import NavStyle, SectionId
from transcriptx.web.action_menus.render import render_configured_actions
from transcriptx.web.cache_helpers import (
    cached_get_available_modules,
    cached_get_default_modules,
    cached_get_default_modules_for_paths,
    cached_get_module_info_list,
    cached_list_groups,
    cached_transcript_summary_for_path,
    get_cached_list_transcript_picker_options,
    transcript_summary_signature,
)
from transcriptx.web.components.action_links import render_action_link
from transcriptx.web.components.analysis_preset_controls import (
    apply_custom_qa_to_plan,
    format_preset_label,
    render_analysis_preset_selector,
    render_effective_module_summary,
)
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.llm_custom_qa_picker import render_custom_qa_picker
from transcriptx.web.components.llm_model_selector import render_compact_llm_setup
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.progress_panel import (
    SNAPSHOT_KEY,
    StreamlitProgressCallback,
    render_progress_panel,
)
from transcriptx.web.components.recent_run_row import render_recent_run_actions
from transcriptx.web.navigation import make_session_path_resolver
from transcriptx.web.page_modules.batch_ops import render_batch_analysis_panel
from transcriptx.web.services.group_service import GroupService
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.services.transcript_context_resolver import paths_match
from transcriptx.web.state import (
    SELECTBOX_PLACEHOLDER_GROUP,
    SELECTBOX_PLACEHOLDER_TRANSCRIPT,
    set_page_flash,
)
from transcriptx.web.transcript_option_format import (
    format_transcript_option_with_speaker_status,
)

_RUN_ANALYSIS_DESCRIPTION = (
    "Choose a target (transcript, group, or batch), an analysis preset, "
    "optional custom questions, and model setup — then run."
)
_KEY_LAST_SUCCESS = "run_analysis_last_success"
_RUN_ANALYSIS_TARGET_KEY = "run_analysis_target"
_PENDING_LAUNCH_KEY = "run_analysis_pending_launch"


def _normalize_run_analysis_target(*, group_target_available: bool) -> str:
    """Coerce persisted target before the control binds; preserve explicit Batch."""
    allowed = {"Transcript", "Batch"}
    if group_target_available:
        allowed.add("Group")
    current = st.session_state.get(_RUN_ANALYSIS_TARGET_KEY)
    if current in allowed:
        return str(current)
    st.session_state[_RUN_ANALYSIS_TARGET_KEY] = "Transcript"
    return "Transcript"


def _store_last_success(
    *,
    run_dir: Path,
    transcript_path: Path | None,
    subject_type: str,
    modules: list[str],
) -> None:
    st.session_state[_KEY_LAST_SUCCESS] = {
        "run_dir": str(run_dir),
        "run_id": run_dir.name,
        "transcript_path": str(transcript_path) if transcript_path else "",
        "subject_type": subject_type,
        "modules": list(modules),
    }


def _run_summary_from_last_success(payload: dict) -> RunSummary | None:
    run_dir_raw = payload.get("run_dir")
    run_id = payload.get("run_id")
    if not run_dir_raw or not run_id:
        return None
    run_dir = Path(str(run_dir_raw))
    if not run_dir.is_dir():
        return None
    tp_raw = payload.get("transcript_path") or ""
    transcript_path = Path(str(tp_raw)) if tp_raw else Path()
    try:
        created_at = datetime.fromtimestamp(run_dir.stat().st_mtime)
    except OSError:
        created_at = datetime.now()
    modules = payload.get("modules") or []
    return RunSummary(
        run_dir=run_dir,
        transcript_path=transcript_path,
        run_id=str(run_id),
        created_at=created_at,
        selected_modules=list(modules) if isinstance(modules, list) else [],
        status="completed",
    )


def _render_post_analysis_actions() -> None:
    """Configured action strip immediately under the success flash."""
    payload = st.session_state.get(_KEY_LAST_SUCCESS)
    if not isinstance(payload, dict):
        return
    run = _run_summary_from_last_success(payload)
    if run is None:
        return

    subject_type = payload.get("subject_type") or "transcript"
    if subject_type == "transcript":
        render_recent_run_actions(
            run,
            row_index=0,
            key_prefix="post_run",
            section=SectionId.RUN_ANALYSIS_COMPLETE,
        )
        return

    identity = build_canonical_identity(
        subject_type="group",
        subject_id=run.run_dir.parent.name,
        run_id=run.run_dir.name,
        run_dir=run.run_dir,
    )
    ctx = ActionContext(
        identity=identity,
        widget_identity=f"post_run_group_{run.run_id}",
        nav_style=NavStyle.ON_CLICK,
        instance_prefix="post_run_group",
        run_completed=True,
        export_supported=False,
        rename_supported=False,
    )
    render_configured_actions(SectionId.RUN_ANALYSIS_COMPLETE, ctx)


def _truncate_label(text: str, *, max_chars: int = 28) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _execute_pending_launch(
    pending: dict[str, Any],
    *,
    progress: StreamlitProgressCallback | None = None,
) -> None:
    """Execute a snapshotted request; sole launch authority after Run click.

    Prefer a bound ``StreamlitProgressCallback`` (with ``render_slot``) so the
    progress panel updates live during the blocking run. A spinner alone would
    hide the module count / bar that users expect to watch.
    """
    analysis_ctrl = AnalysisController()
    target_type = pending["target_type"]
    modules = list(pending["modules"])
    st.session_state[SNAPSHOT_KEY] = make_initial_snapshot(len(modules))
    if progress is None:
        progress = StreamlitProgressCallback()
    snapshot = st.session_state[SNAPSHOT_KEY]
    progress.refresh_panel()

    request = pending["request"]
    selected_group = pending.get("selected_group")
    transcript_path = pending.get("transcript_path")
    if transcript_path is not None:
        transcript_path = Path(transcript_path)

    def run_fn():
        if target_type == "Transcript":
            return analysis_ctrl.run_analysis(
                request, progress=progress, snapshot=snapshot
            )
        return analysis_ctrl.run_group_analysis(
            request, progress=progress, snapshot=snapshot
        )

    # No st.spinner: the progress panel is the run affordance. A spinner would
    # dominate the viewport while the bar/count stayed frozen at 0 / N.
    try:
        with capture_output() as (stdout_buf, stderr_buf):
            result = run_fn()
    finally:
        st.session_state["analysis_run_in_progress"] = False
        st.session_state.pop(_PENDING_LAUNCH_KEY, None)
        progress.refresh_panel()

    captured = stdout_buf.getvalue() + stderr_buf.getvalue()

    if result.success:
        from transcriptx.web.cache_helpers import clear_run_listing_caches

        clear_run_listing_caches()
        rd = result.run_dir
        if target_type == "Transcript":
            st.session_state["subject_type"] = "transcript"
            st.session_state["subject_id"] = rd.parent.name
            subject_type = "transcript"
        else:
            st.session_state["subject_type"] = "group"
            st.session_state["subject_id"] = selected_group
            subject_type = "group"
        st.session_state["run_id"] = rd.name
        _store_last_success(
            run_dir=rd,
            transcript_path=transcript_path if target_type == "Transcript" else None,
            subject_type=subject_type,
            modules=list(result.modules_executed or []),
        )
        set_page_flash("success", f"Analysis completed. Output: `{rd}`")
        if result.modules_executed:
            st.caption(f"Modules run: {', '.join(result.modules_executed)}")
        agg_warns = getattr(result, "aggregation_warnings", None) or []
        if agg_warns:
            chart_failed_n = sum(
                1
                for w in agg_warns
                if isinstance(w, dict) and w.get("code") == "GROUP_CHART_FAILED"
            )
            if chart_failed_n:
                st.error(
                    f"Group chart generation failed for {chart_failed_n} "
                    "aggregation step(s). Charts for those modules may be missing. "
                    "See **Aggregation notices** below."
                )
            with st.expander(
                f"Aggregation notices ({len(agg_warns)})",
                expanded=bool(chart_failed_n),
            ):
                for w in agg_warns[:50]:
                    if isinstance(w, dict):
                        code = w.get("code") or "—"
                        msg = w.get("message") or ""
                        ak = w.get("aggregation_key")
                        st.markdown(
                            f"- **`{code}`**"
                            + (f" (`{ak}`)" if ak else "")
                            + f": {msg}"
                        )
                    else:
                        st.markdown(f"- {w!s}")
                if len(agg_warns) > 50:
                    st.caption(
                        f"… and {len(agg_warns) - 50} more "
                        "(see aggregation_warnings.json in the run directory)."
                    )
        if result.warnings:
            for w in result.warnings[:5]:
                st.warning(w)
        if result.errors:
            st.warning(f"{len(result.errors)} warning(s) during run:")
            for e in result.errors[:5]:
                st.caption(f"  • {e}")
    else:
        st.error("Analysis failed.")
        for e in result.errors:
            st.error(e)

    if captured:
        with st.expander("Full log output"):
            st.text(captured)

    st.rerun()


def _resolve_transcript_selection(
    transcript_options: tuple[str, ...],
    transcript_labels: tuple[str, ...],
) -> Path | None:
    """Transcript selectbox + cheap context sync (fragment-local)."""
    default_idx = SubjectService.index_in_path_options(
        st.session_state, list(transcript_options)
    )
    transcript_choice = st.selectbox(
        "Transcript",
        range(len(transcript_options) + 1),
        format_func=lambda i: (
            SELECTBOX_PLACEHOLDER_TRANSCRIPT
            if i == 0
            else (
                transcript_labels[i - 1]
                if i - 1 < len(transcript_labels)
                else ""
            )
        ),
        index=default_idx,
        key="run_analysis_transcript",
    )
    if transcript_choice <= 0:
        return None
    transcript_path = Path(transcript_options[transcript_choice - 1])
    current = SubjectService.current_transcript_path(st.session_state)

    if current is None or not paths_match(current, transcript_path):
        SubjectService.set_transcript_context_from_path(
            st.session_state,
            transcript_path,
            # Lazy resolver: indexed paths never touch rich session listing.
            session_resolver=make_session_path_resolver(),
        )
    # Optional caption for the selection only (not the full library).
    try:
        summary = cached_transcript_summary_for_path(
            str(transcript_path),
            transcript_summary_signature(transcript_path),
        )
    except Exception:
        summary = None
    if summary is not None:
        st.caption(format_transcript_option_with_speaker_status(summary))
    return transcript_path


def _resolve_group_selection(
    groups: tuple[Group, ...],
) -> tuple[Group | None, tuple[str, ...]]:
    """Group selectbox + member path resolution (fragment-local)."""
    group_options = {g.uuid: g for g in groups}
    group_labels = {
        g.uuid: f"{g.name or 'Unnamed'} • {len(g.transcript_file_uuids or [])} transcripts"
        for g in groups
    }
    group_keys = list(group_options.keys())
    default_group_idx = 0
    current_subject = st.session_state.get("subject_id")
    if (
        st.session_state.get("subject_type") == "group"
        and current_subject in group_options
    ):
        default_group_idx = group_keys.index(current_subject) + 1
    selected_uuid = st.selectbox(
        "Group",
        [""] + group_keys,
        format_func=lambda key: (
            SELECTBOX_PLACEHOLDER_GROUP
            if key == ""
            else group_labels.get(key, key)
        ),
        index=default_group_idx,
        key="run_analysis_group",
    )
    selected_group = group_options.get(selected_uuid) if selected_uuid else None
    if not selected_group:
        return None, ()
    members = GroupService.get_members(selected_group)
    resolved_member_paths = tuple(
        str(Path(m.file_path))
        for m in members
        if getattr(m, "file_path", None) and Path(m.file_path).exists()
    )
    return selected_group, resolved_member_paths


@st.fragment
def _run_analysis_config_and_launch_fragment(
    target_type: str,
    *,
    transcript_options: tuple[str, ...] = (),
    transcript_labels: tuple[str, ...] = (),
    groups: tuple[Group, ...] = (),
) -> None:
    """Selection + config + sticky footer; fragment-reruns on transcript/group change.

    Keeping the transcript/group selectboxes inside this fragment avoids a full-app
    rerun (sidebar + shell) on every dropdown change after the light picker loads.
    """
    transcript_path: Path | None = None
    selected_group: Group | None = None
    transcript_targets: tuple[str, ...] = ()

    if target_type == "Transcript":
        transcript_path = _resolve_transcript_selection(
            transcript_options, transcript_labels
        )
    else:
        selected_group, transcript_targets = _resolve_group_selection(groups)

    available = list(cached_get_available_modules())
    if target_type == "Transcript" and transcript_path:
        cached_get_default_modules(str(transcript_path))
        transcript_targets = (str(transcript_path),)
    elif target_type == "Group" and transcript_targets:
        cached_get_default_modules_for_paths(transcript_targets, for_group=True)
        group_supported = {
            info["name"]
            for info in cached_get_module_info_list()
            if info.get("supports_group", True)
        }
        available = [module_id for module_id in available if module_id in group_supported]

    analysis_target = "group" if target_type == "Group" else "transcript"

    resolved = render_analysis_preset_selector(
        key_prefix="run_analysis",
        target=analysis_target,  # type: ignore[arg-type]
        transcript_targets=transcript_targets or None,
        available_modules=available,
    )

    qa_request_questions, qa_effective, custom_qa_execution = render_custom_qa_picker(
        key_prefix="run_analysis_qa",
        always_show=True,
    )
    plan = apply_custom_qa_to_plan(resolved, custom_qa_execution=custom_qa_execution)
    render_effective_module_summary(
        plan,
        preset=resolved.preset,
        key_prefix="run_analysis",
        qa_key_prefix="run_analysis_qa",
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
        llm_selection, llm_gates, model_label = render_compact_llm_setup(
            key_prefix="run_analysis_llm",
            selected_modules=selected_modules,
            include_group=(target_type == "Group"),
        )
    finally:
        if _qa_ui_token is not None:
            reset_custom_qa_questions(_qa_ui_token)

    can_launch = bool(selected_modules) and not llm_gates
    disable_reason = ""
    if not selected_modules:
        disable_reason = "Select at least one module."
    elif llm_gates:
        disable_reason = llm_gates[0]
    if target_type == "Transcript":
        if transcript_path is None or not transcript_path.exists():
            can_launch = False
            disable_reason = disable_reason or "Select a transcript."
    elif selected_group is None:
        can_launch = False
        disable_reason = disable_reason or "Select a group."

    subject_label = "—"
    if target_type == "Transcript" and transcript_path is not None:
        subject_label = _truncate_label(transcript_path.stem)
    elif target_type == "Group" and selected_group is not None:
        subject_label = _truncate_label(selected_group.name or selected_group.uuid)

    n_questions = 0
    if isinstance(qa_request_questions, list):
        n_questions = len(qa_request_questions)
    q_part = (
        f"{n_questions} custom question" + ("s" if n_questions != 1 else "")
        if custom_qa_execution
        else "custom questions skipped"
    )
    summary_html = (
        f'<span class="tx-ellipsis">{subject_label}</span> · '
        f"{format_preset_label(resolved.preset)} · "
        f"{len(selected_modules)} modules · {q_part} · {model_label}"
    )

    st.markdown(
        '<div class="tx-run-analysis-footer" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    with st.container():
        st.markdown(
            f'<div class="tx-run-analysis-footer-summary">{summary_html}</div>',
            unsafe_allow_html=True,
        )
        cols = st.columns([4, 1.4])
        with cols[0]:
            if disable_reason and not can_launch:
                st.caption(disable_reason)
        with cols[1]:
            launch = st.button(
                "Run analysis",
                type="primary",
                key="run_analysis_launch",
                disabled=not can_launch,
                width="stretch",
            )

    if not launch:
        return

    analysis_ctrl = AnalysisController()
    if target_type == "Transcript":
        if not transcript_path or not transcript_path.exists():
            st.error("Please select a valid transcript.")
            return
        request: AnalysisRequest | GroupAnalysisRequest = AnalysisRequest(
            transcript_path=transcript_path,
            mode=resolved.mode,
            modules=selected_modules,
            profile=resolved.profile,
            analysis_preset=resolved.preset,
            llm_model_selection=llm_selection,
            llm_custom_qa_questions=qa_request_questions,
        )
        errors = analysis_ctrl.validate_readiness(request)
    else:
        if not selected_group:
            st.error("Please select a group.")
            return
        request = GroupAnalysisRequest(
            group_uuid=selected_group.uuid,
            mode=resolved.mode,
            modules=selected_modules,
            profile=resolved.profile,
            analysis_preset=resolved.preset,
            include_unidentified_speakers=False,
            llm_model_selection=llm_selection,
            llm_custom_qa_questions=qa_request_questions,
        )
        errors = analysis_ctrl.validate_group_readiness(request)

    if errors:
        for e in errors:
            st.error(e)
        return

    st.session_state.pop(_KEY_LAST_SUCCESS, None)
    st.session_state[_PENDING_LAUNCH_KEY] = {
        "target_type": target_type,
        "modules": list(selected_modules),
        "request": request,
        "transcript_path": str(transcript_path) if transcript_path else None,
        "selected_group": (
            selected_group.group_id if selected_group is not None else None
        ),
        "form_cleared": False,
        "started": False,
        "footer_summary": summary_html,
    }
    st.session_state[SNAPSHOT_KEY] = make_initial_snapshot(len(selected_modules))
    st.session_state["analysis_run_in_progress"] = True
    st.rerun()


def render_run_analysis_page() -> None:
    """Render the Run Analysis page with form and execution."""
    config = get_config()
    group_analysis_enabled = getattr(config.group_analysis, "enabled", False)
    group_target_available = group_analysis_enabled

    _normalize_run_analysis_target(group_target_available=group_target_available)

    render_page_shell(
        "Run Analysis",
        _RUN_ANALYSIS_DESCRIPTION,
        badges=None,
        actions=None,
    )

    # Post-run strip is for the completed run only — hide while a launch is active
    # so links never point at a stale prior run_id mid-pipeline.
    if (
        st.session_state.get(_RUN_ANALYSIS_TARGET_KEY) != "Batch"
        and not st.session_state.get("analysis_run_in_progress", False)
    ):
        _render_post_analysis_actions()

    target_options = ["Transcript"]
    if group_target_available:
        target_options.append("Group")
    target_options.append("Batch")

    current = st.session_state.get(_RUN_ANALYSIS_TARGET_KEY, "Transcript")
    if current not in target_options:
        current = "Transcript"
        st.session_state[_RUN_ANALYSIS_TARGET_KEY] = current

    target_type = st.segmented_control(
        "Target",
        options=target_options,
        key=_RUN_ANALYSIS_TARGET_KEY,
    )
    if target_type is None:
        target_type = st.session_state.get(_RUN_ANALYSIS_TARGET_KEY, "Transcript")

    if not group_target_available:
        st.caption("Enable group analysis in config to run analysis on groups.")
    if target_type == "Group" and group_target_available:
        st.caption(
            "Group scope: modules differ—registry-backed aggregate charts, special paths "
            "(e.g. wordclouds), data-only (e.g. temporal dynamics), or blob-only (summary). "
            "See docs/groups/group_analysis_module_outputs.md in the project."
        )

    if target_type == "Batch":
        render_batch_analysis_panel()
        return

    # Three-phase launch so Streamlit can drop the prior form widgets:
    # 1) click stores pending + rerun
    # 2) paint progress only + form_cleared + rerun (ends script → clears form)
    # 3) paint progress + execute (blocking; form stays gone)
    pending = st.session_state.get(_PENDING_LAUNCH_KEY)
    if st.session_state.get("analysis_run_in_progress", False) and isinstance(
        pending, dict
    ):
        summary = pending.get("footer_summary") or "Running analysis…"
        st.markdown(
            '<div class="tx-run-analysis-footer" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        with st.container():
            st.markdown(
                f'<div class="tx-run-analysis-footer-summary">{summary}</div>',
                unsafe_allow_html=True,
            )
            progress_slot = st.empty()
            snapshot = st.session_state.get(SNAPSHOT_KEY)
            if snapshot is not None:
                with progress_slot.container():
                    render_progress_panel(snapshot)
            else:
                with progress_slot.container():
                    st.info("Analysis is running…")
        if not pending.get("form_cleared"):
            pending["form_cleared"] = True
            st.session_state[_PENDING_LAUNCH_KEY] = pending
            st.rerun()
            return
        if not pending.get("started"):
            pending["started"] = True
            st.session_state[_PENDING_LAUNCH_KEY] = pending
            progress = StreamlitProgressCallback(render_slot=progress_slot)
            _execute_pending_launch(pending, progress=progress)
        return

    if st.session_state.get("analysis_run_in_progress", False):
        snapshot = st.session_state.get(SNAPSHOT_KEY)
        if snapshot is not None:
            render_progress_panel(snapshot)
        else:
            st.info("Analysis is running…")
        return

    transcript_options: tuple[str, ...] = ()
    transcript_labels: tuple[str, ...] = ()
    groups: tuple[Group, ...] = ()

    if target_type == "Transcript":
        picker_options = get_cached_list_transcript_picker_options()
        if not picker_options:
            render_empty_state(
                "no_results_yet",
                "No transcripts found",
                "Add transcript JSON files to your configured diarized folder or register them from the Library.",
                primary_action=("Library", "Library"),
                secondary_action=("Home", "Home"),
            )
            return
        transcript_options = tuple(opt.path for opt in picker_options)
        transcript_labels = tuple(opt.label for opt in picker_options)
    else:
        listed = cached_list_groups()
        if not listed:
            render_empty_state(
                "no_results_yet",
                "No groups yet",
                "Create a group on the Groups page before running group analysis.",
                primary_action=("Groups", "Groups"),
                secondary_action=("Library", "Library"),
            )
            return
        groups = tuple(listed)

    last_snapshot = st.session_state.get(SNAPSHOT_KEY)
    if last_snapshot and last_snapshot.get("status") in ("completed", "failed"):
        with st.expander("Last run progress", expanded=False):
            render_progress_panel(last_snapshot)
            if last_snapshot.get("status") == "completed":
                if render_action_link(
                    "Open Viewer Overview",
                    key="last_run_progress_open_overview",
                    icon=":material/folder_open:",
                ):
                    st.session_state["page"] = "Overview"
                    st.rerun()

    _run_analysis_config_and_launch_fragment(
        target_type,
        transcript_options=transcript_options,
        transcript_labels=transcript_labels,
        groups=groups,
    )
