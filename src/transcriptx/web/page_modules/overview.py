"""
Overview dashboard page for TranscriptX Studio.

Export selection widgets run in ``@st.fragment`` so radio/select changes do not
trigger a full-app rerun (avoids the dimming overlay on each export mode click).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd
from transcriptx.core.pipeline.manifest_loader import load_run_results
from transcriptx.core.pipeline.run_outcome_truth import (
    project_canonical_outcomes,
    project_group_outcomes,
)

from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.module_option_format import format_module_option
from transcriptx.web.module_ui_groups import module_sort_key, order_module_ids
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services import ArtifactService, RunIndex, SubjectService

_OVERVIEW_HELP_PREREQ = "**Overview** shows artifact counts, module summaries, and export options for one run."
_OVERVIEW_HELP_LOADED = (
    "**Overview** aggregates artifacts for the current run. Warnings here reflect "
    "manifest checks, not full pipeline logs."
)


def _load_run_results(run_root: Path | str) -> dict | None:
    """Load run_results.json if present (run-level summary: modules run / skipped / why)."""
    path = Path(run_root) / "run_results.json"
    if not path.exists():
        return None
    try:
        return load_run_results(path)
    except Exception:
        return None


def _parse_run_datetime(run_id: str) -> str:
    """Parse run_id to extract and format date/time.

    Run ID format: YYYYMMDD_HHMMSS_<hash>
    Returns formatted string like: "2026-01-24 08:19:59"
    """
    try:
        # Extract date/time portion (first 15 characters: YYYYMMDD_HHMMSS)
        if "_" in run_id:
            date_time_str = run_id.split("_")[0] + "_" + run_id.split("_")[1]
            dt = datetime.strptime(date_time_str, "%Y%m%d_%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        pass
    return run_id  # Fallback to raw run_id if parsing fails


@st.fragment
def _overview_export_fragment(run_root: Path, artifacts: list[Artifact]) -> None:
    """High-churn export UI; reruns only this block when export mode changes."""
    st.subheader("Export")
    export_mode = st.radio(
        "Export Options",
        [
            "All",
            "Module",
            "Speaker",
            "Charts Only",
            "Static Charts Only",
            "Data Only",
            "Custom Selection",
        ],
        key="overview_export_mode",
    )
    selected_artifacts = artifacts
    if export_mode == "Module":
        module_options = order_module_ids({a.module for a in artifacts if a.module})
        module_choice = st.selectbox(
            "Module",
            module_options,
            format_func=format_module_option,
            key="overview_export_module",
        )
        selected_artifacts = [a for a in artifacts if a.module == module_choice]
    elif export_mode == "Speaker":
        speaker_options = sorted({a.speaker for a in artifacts if a.speaker})
        speaker_choice = st.selectbox(
            "Speaker",
            speaker_options,
            key="overview_export_speaker",
        )
        selected_artifacts = [a for a in artifacts if a.speaker == speaker_choice]
    elif export_mode == "Charts Only":
        selected_artifacts = [a for a in artifacts if a.kind.startswith("chart")]
    elif export_mode == "Static Charts Only":
        selected_artifacts = [a for a in artifacts if a.kind == "chart_static"]
    elif export_mode == "Data Only":
        selected_artifacts = [a for a in artifacts if a.kind.startswith("data")]
    elif export_mode == "Custom Selection":
        options = {a.id: a.rel_path for a in artifacts}
        chosen = st.multiselect(
            "Artifacts",
            list(options.keys()),
            format_func=lambda key: options.get(key, key),
            key="overview_export_artifacts",
        )
        selected_artifacts = [a for a in artifacts if a.id in chosen]

    if not selected_artifacts:
        st.info("No artifacts selected for export.")
        return

    total_bytes = sum(a.bytes for a in selected_artifacts)
    st.caption(f"Selection size: {total_bytes / (1024 * 1024):.1f} MB")

    confirm_large = True
    if total_bytes > 500 * 1024 * 1024:
        st.warning("Large export (> 500MB). Confirm before exporting.")
        confirm_large = st.checkbox(
            "I understand this may take time.",
            key="overview_export_confirm_large",
        )
    if total_bytes > 2 * 1024 * 1024 * 1024:
        st.error("Export exceeds 2GB hard cap.")
        return

    if st.button(
        "Create Export", disabled=not confirm_large, key="overview_create_export"
    ):
        export_path = ArtifactService.zip_artifacts(
            run_root, [a.id for a in selected_artifacts]
        )
        if export_path:
            try:
                payload = ArtifactService.read_for_download(export_path)
                st.download_button(
                    "Download Export",
                    data=payload,
                    file_name=export_path.name,
                    key="overview_download_export",
                )
            except Exception as exc:
                st.error(f"Export failed: {exc}")


def render_overview() -> None:
    subject = SubjectService.resolve_current_subject(st.session_state)
    run_id = st.session_state.get("run_id")
    if not subject or not run_id:
        render_page_shell(
            "Overview",
            "Summary of artifacts and health for the selected run.",
            badges=None,
            actions=None,
        )
        render_empty_state(
            "missing_prerequisite",
            "Select a subject and run",
            "Use the sidebar to choose a transcript or group, then pick a run.",
            primary_action=("Open Library", "Library"),
            secondary_action=("Run Analysis", "Run Analysis"),
        )
        render_page_help(_OVERVIEW_HELP_PREREQ)
        return
    run_root = RunIndex.get_run_root(
        subject.scope,
        run_id,
        subject_id=subject.subject_id,
    )

    run_datetime = _parse_run_datetime(run_id)

    artifacts = ArtifactService.list_artifacts(run_root)
    health = ArtifactService.check_run_health(run_root)
    status = health.get("status")
    badge_health = "Artifact Health: Healthy"
    if status == "error":
        badge_health = "Artifact Health: Missing"
    elif status == "warning" or health.get("warnings"):
        badge_health = "Artifact Health: Partial"

    render_page_shell(
        "Overview",
        f"Run started: {run_datetime}. Browse artifacts and export selections.",
        badges=[badge_health],
        actions=None,
    )

    if not artifacts:
        render_empty_state(
            "no_results_yet",
            "No artifacts for this run",
            "This run folder exists but lists no artifacts yet, or analysis did not write outputs.",
            primary_action=("Run Analysis", "Run Analysis"),
            secondary_action=("Diagnostics", "Diagnostics"),
        )
        render_page_help(_OVERVIEW_HELP_LOADED)
        return

    has_errors = bool(health.get("errors"))
    has_warnings = bool(health.get("warnings"))
    has_issues = status in ("error", "warning") or has_errors or has_warnings

    if status == "error":
        st.error("🔴 Errors detected in this run.")
    elif status == "warning":
        st.warning("🟠 Warnings detected in this run.")

    # Only show re-scan button when there are health issues
    if has_issues:
        if st.button("Re-scan health checks"):
            st.cache_data.clear()
            st.rerun()

    if health.get("errors"):
        with st.expander("Errors"):
            for item in health["errors"]:
                st.write(f"- {item}")
    if health.get("warnings"):
        with st.expander("Warnings"):
            for item in health["warnings"]:
                st.write(f"- {item}")

    # Run-level execution summary (canonical outcomes), separate from artifact health.
    run_results = _load_run_results(run_root)
    if run_results:
        if (Path(run_root) / "group_member_runs.json").exists():
            try:
                group_truth = project_group_outcomes(run_root)
                outcomes = group_truth.group_outcomes
            except Exception:
                outcomes = project_canonical_outcomes(run_results)
        else:
            outcomes = project_canonical_outcomes(run_results)
        skipped = [o for o in outcomes if o.status in {"skipped", "blocked"}]
        failed = [o for o in outcomes if o.status == "failed"]
        preset_explanation = run_results.get("preset_explanation")
        if skipped or failed or preset_explanation:
            with st.expander(
                "Run summary (included / excluded)",
                expanded=bool(skipped or failed),
            ):
                if preset_explanation:
                    st.caption("Preset explanation")
                    st.text(preset_explanation)
                if failed:
                    st.caption("Failed modules")
                    for row in failed:
                        detail = row.reason or ""
                        if row.error_code:
                            prefix = f"[{row.error_code}]"
                            detail = f"{prefix} {detail}".strip()
                        st.write(
                            f"- **{row.module_id}**: {detail or row.error_code or 'failed'}"
                        )
                if skipped:
                    st.caption("Skipped modules (reason)")
                    for s in skipped:
                        st.write(f"- **{s.module_id}** ({s.status}): {s.reason or ''}")

    total_files = len(artifacts)
    chart_count = len([a for a in artifacts if a.kind.startswith("chart")])
    data_count = len([a for a in artifacts if a.kind.startswith("data")])
    total_size = sum(a.bytes for a in artifacts)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Artifacts", total_files)
    with col2:
        st.metric("Charts", chart_count)
    with col3:
        st.metric("Data Files", data_count)
    with col4:
        st.metric("Disk Size", f"{total_size / (1024 * 1024):.1f} MB")

    st.divider()
    st.subheader("Per-Module Summary")
    module_map: dict[str, dict[str, object]] = {}
    for artifact in artifacts:
        module = artifact.module or "other"
        module_map.setdefault(module, {"charts": 0, "data": 0, "last": None})
        if artifact.kind.startswith("chart"):
            module_map[module]["charts"] += 1
        if artifact.kind.startswith("data"):
            module_map[module]["data"] += 1
        module_map[module]["last"] = max(
            module_map[module]["last"] or artifact.mtime, artifact.mtime
        )

    # Create DataFrame for table display
    table_data = []
    for module, stats in sorted(
        module_map.items(), key=lambda item: module_sort_key(item[0])
    ):
        table_data.append(
            {
                "Module": module,
                "Charts": stats["charts"],
                "Data Files": stats["data"],
                "Last Updated": stats["last"] if stats["last"] else "N/A",
            }
        )

    df = pd.DataFrame(table_data)

    # Display in a scrollable container
    st.markdown(
        """
        <style>
        .module-summary-container {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #e0e0e0;
            border-radius: 0.5rem;
            padding: 1rem;
            background-color: #fafafa;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            height=min(
                400, 50 + len(df) * 35
            ),  # Dynamic height based on rows, max 400px
        )

    st.divider()
    _overview_export_fragment(run_root, artifacts)
    render_page_help(_OVERVIEW_HELP_LOADED)
