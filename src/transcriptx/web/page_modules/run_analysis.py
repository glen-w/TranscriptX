"""
Run Analysis page - configure and execute single-transcript or group analysis.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.app.controllers.analysis_controller import AnalysisController
from transcriptx.core.domain.group import Group
from transcriptx.app.models.requests import AnalysisRequest, GroupAnalysisRequest
from transcriptx.app.output_capture import capture_output
from transcriptx.app.progress import make_initial_snapshot
from transcriptx.core.utils.config import get_config
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.state import (
    SELECTBOX_PLACEHOLDER_GROUP,
    SELECTBOX_PLACEHOLDER_TRANSCRIPT,
    set_page_flash,
    try_page_toast,
)
from transcriptx.web.components.progress_panel import (
    SNAPSHOT_KEY,
    StreamlitProgressCallback,
    render_progress_panel,
)
from transcriptx.web.cache_helpers import (
    get_cached_list_transcripts,
    cached_list_groups,
    cached_get_available_modules,
    cached_get_default_modules,
    cached_get_default_modules_for_paths,
    cached_get_module_info_list,
)
from transcriptx.web.module_option_format import format_module_option
from transcriptx.web.services.group_service import GroupService
from transcriptx.web.transcript_option_format import (
    format_transcript_option_with_speaker_status,
)
from transcriptx.web.navigation import make_session_path_resolver
from transcriptx.web.services.subject_service import SubjectService

_RUN_ANALYSIS_HELP = (
    "**Quick** uses a lighter preset; **full** lets you pick a profile. "
    "Recommended modules adapt to the selected transcript(s)."
)


@st.fragment
def _run_analysis_config_and_launch_fragment(
    target_type: str,
    transcript_path: Path | None,
    selected_group: Group | None,
    available: tuple[str, ...],
    default_modules: tuple[str, ...],
) -> None:
    """
    Config widgets + launch + post-run UI in one fragment so module multiselect
    does not rerun sidebar/context bar. Target selection stays in the parent
    (full rerun when transcript/group changes). Launch/progress remain explicit
    commit paths with full ``st.rerun()`` after completion/navigation.
    """
    analysis_ctrl = AnalysisController()
    mode = st.radio(
        "Analysis mode", ["quick", "full"], horizontal=True, key="run_analysis_mode"
    )
    st.caption(
        "**Quick** — faster preset with fewer heavy modules. **Full** — profile-driven, more artifacts."
    )
    profile = None
    if mode == "full":
        profile = st.selectbox(
            "Profile",
            ["balanced", "academic", "business", "casual", "technical", "interview"],
            key="run_analysis_profile",
        )

    use_defaults = st.checkbox(
        "Use recommended modules", value=True, key="run_analysis_use_defaults"
    )
    if use_defaults:
        selected_modules = list(default_modules)
        st.caption(
            f"**{len(selected_modules)} modules** (recommended): "
            f"{', '.join(selected_modules[:8])}{'...' if len(selected_modules) > 8 else ''}"
        )
    else:
        selected_modules = st.multiselect(
            "Select modules",
            list(available),
            default=list(default_modules[:5]) if default_modules else [],
            format_func=format_module_option,
            key="run_analysis_modules",
        )
        st.caption(f"**{len(selected_modules)} modules** selected.")

    can_launch = bool(selected_modules)
    if target_type == "Transcript":
        can_launch = (
            can_launch and transcript_path is not None and transcript_path.exists()
        )
    else:
        can_launch = can_launch and selected_group is not None

    if st.button(
        "▶ Run Analysis",
        type="primary",
        key="run_analysis_launch",
        disabled=not can_launch,
    ):
        if not selected_modules:
            st.error("Please select at least one module.")
            return

        if target_type == "Transcript":
            if not transcript_path or not transcript_path.exists():
                st.error("Please select a valid transcript.")
                return

            request = AnalysisRequest(
                transcript_path=transcript_path,
                mode=mode,
                modules=selected_modules,
                profile=profile,
            )

            errors = analysis_ctrl.validate_readiness(request)
            if errors:
                for e in errors:
                    st.error(e)
                return

            def run_fn():
                return analysis_ctrl.run_analysis(
                    request, progress=progress, snapshot=snapshot
                )

        else:
            if not selected_group:
                st.error("Please select a group.")
                return

            group_request = GroupAnalysisRequest(
                group_uuid=selected_group.uuid,
                mode=mode,
                modules=selected_modules,
                profile=profile,
                include_unidentified_speakers=False,
            )

            errors = analysis_ctrl.validate_group_readiness(group_request)
            if errors:
                for e in errors:
                    st.error(e)
                return

            def run_fn():
                return analysis_ctrl.run_group_analysis(
                    group_request, progress=progress, snapshot=snapshot
                )

        st.session_state[SNAPSHOT_KEY] = make_initial_snapshot(len(selected_modules))
        st.session_state["analysis_run_in_progress"] = True

        progress = StreamlitProgressCallback()
        snapshot = st.session_state[SNAPSHOT_KEY]

        with st.spinner("Running analysis…"):
            try:
                with capture_output() as (stdout_buf, stderr_buf):
                    result = run_fn()
            finally:
                st.session_state["analysis_run_in_progress"] = False

            captured = stdout_buf.getvalue() + stderr_buf.getvalue()

        if result.success:
            from transcriptx.web.cache_helpers import clear_run_listing_caches

            clear_run_listing_caches()
            rd = result.run_dir
            if target_type == "Transcript":
                st.session_state["subject_type"] = "transcript"
                st.session_state["subject_id"] = rd.parent.name
            else:
                st.session_state["subject_type"] = "group"
                st.session_state["subject_id"] = selected_group.group_id
            st.session_state["run_id"] = rd.name
            set_page_flash(
                "success",
                f"Analysis completed. Output: `{rd}`",
            )
            try_page_toast("Analysis completed.")
            st.success(f"Analysis completed successfully. Output: `{rd}`")
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
                            f"… and {len(agg_warns) - 50} more (see aggregation_warnings.json in the run directory)."
                        )
            oc1, oc2, oc3 = st.columns(3)
            with oc1:
                if st.button("Open Overview", key="post_run_overview"):
                    st.session_state["page"] = "Overview"
                    st.rerun()
            with oc2:
                if st.button("Open Charts", key="post_run_charts"):
                    st.session_state["page"] = "Charts"
                    st.rerun()
            with oc3:
                if st.button("Open Data", key="post_run_data"):
                    st.session_state["page"] = "Artifacts"
                    st.rerun()
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


def render_run_analysis_page() -> None:
    """Render the Run Analysis page with form and execution."""
    render_page_shell(
        "Run Analysis",
        "Configure modules and run analysis on one transcript or a group.",
        badges=None,
        actions=None,
    )

    config = get_config()
    group_analysis_enabled = getattr(config.group_analysis, "enabled", False)
    group_target_available = group_analysis_enabled

    target_options = ["Transcript"]
    if group_target_available:
        target_options.append("Group")
    target_type = st.radio(
        "Target",
        target_options,
        horizontal=True,
        key="run_analysis_target",
    )
    if not group_target_available and "Group" not in target_options:
        st.caption("Enable group analysis in config to run analysis on groups.")
    if group_target_available:
        st.caption(
            "Group scope: modules differ—registry-backed aggregate charts, special paths (e.g. wordclouds), "
            "data-only (e.g. temporal dynamics), or blob-only (summary). "
            "See docs/groups/group_analysis_module_outputs.md in the project."
        )

    transcript_path: Path | None = None
    selected_group = None  # set when target is Group
    resolved_member_paths: list[str] = []

    if target_type == "Transcript":
        transcripts = get_cached_list_transcripts()
        transcript_options = [str(t.path) for t in transcripts]
        transcript_labels = [
            format_transcript_option_with_speaker_status(t) for t in transcripts
        ]

        if not transcript_options:
            render_empty_state(
                "no_results_yet",
                "No transcripts found",
                "Add transcript JSON files to your configured diarized folder or register them from the Library.",
                primary_action=("Library", "Library"),
                secondary_action=("Home", "Home"),
            )
            transcript_path = None
        else:
            default_idx = SubjectService.index_in_path_options(
                st.session_state, transcript_options
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
            transcript_path = (
                Path(transcript_options[transcript_choice - 1])
                if transcript_choice > 0
                else None
            )
            if transcript_path is not None:
                SubjectService.set_transcript_context_from_path(
                    st.session_state,
                    transcript_path,
                    session_resolver=make_session_path_resolver(),
                )
    else:
        groups = cached_list_groups()
        if not groups:
            render_empty_state(
                "no_results_yet",
                "No groups yet",
                "Create a group on the Groups page before running group analysis.",
                primary_action=("Groups", "Groups"),
                secondary_action=("Library", "Library"),
            )
        else:
            group_options = {g.uuid: g for g in groups}
            group_labels = {
                g.uuid: f"{g.name or 'Unnamed'} • {len(g.transcript_file_uuids or [])} transcripts"
                for g in groups
            }
            group_keys = list(group_options.keys())
            selected_uuid = st.selectbox(
                "Group",
                [""] + group_keys,
                format_func=lambda key: (
                    SELECTBOX_PLACEHOLDER_GROUP
                    if key == ""
                    else group_labels.get(key, key)
                ),
                index=0,
                key="run_analysis_group",
            )
            selected_group = group_options.get(selected_uuid) if selected_uuid else None
            if selected_group:
                members = GroupService.get_members(selected_group)
                resolved_member_paths = [
                    str(Path(m.file_path))
                    for m in members
                    if getattr(m, "file_path", None) and Path(m.file_path).exists()
                ]

    available = cached_get_available_modules()
    if target_type == "Transcript" and transcript_path:
        default_modules = cached_get_default_modules(str(transcript_path))
    elif target_type == "Group" and resolved_member_paths:
        default_modules = cached_get_default_modules_for_paths(
            tuple(resolved_member_paths), for_group=True
        )
        group_supported = {
            info["name"]
            for info in cached_get_module_info_list()
            if info.get("supports_group", True)
        }
        available = [
            module_id for module_id in available if module_id in group_supported
        ]
    else:
        default_modules = available[:5] if available else []

    # ------------------------------------------------------------------
    # If a run is in progress, show the live progress panel instead of
    # the launch button.  The snapshot is persisted in session_state so
    # Streamlit reruns rehydrate it without regressing to a generic message.
    # ------------------------------------------------------------------
    if st.session_state.get("analysis_run_in_progress", False):
        snapshot = st.session_state.get(SNAPSHOT_KEY)
        if snapshot is not None:
            render_progress_panel(snapshot)
        else:
            st.info("Analysis is running…")
        render_page_help(_RUN_ANALYSIS_HELP)
        return

    # Show panel for the last run (completed or failed) so the result persists
    # on the page after execution finishes without requiring a manual refresh.
    last_snapshot = st.session_state.get(SNAPSHOT_KEY)
    if last_snapshot and last_snapshot.get("status") in ("completed", "failed"):
        with st.expander("Last run progress", expanded=False):
            render_progress_panel(last_snapshot)
            if last_snapshot.get("status") == "completed":
                if st.button(
                    "Open Viewer Overview", key="last_run_progress_open_overview"
                ):
                    st.session_state["page"] = "Overview"
                    st.rerun()

    _run_analysis_config_and_launch_fragment(
        target_type,
        transcript_path,
        selected_group,
        tuple(available),
        tuple(default_modules),
    )
    render_page_help(_RUN_ANALYSIS_HELP)
