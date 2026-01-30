"""
Overview dashboard page for TranscriptX Studio.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st
import pandas as pd

from transcriptx.web.services import ArtifactService


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


def render_overview() -> None:
    session = st.session_state.get("selected_session")
    run_id = st.session_state.get("selected_run_id")
    if not session or not run_id:
        st.info("Select a session and run to view the overview.")
        return

    # Display run date/time at the top in small text
    run_datetime = _parse_run_datetime(run_id)
    st.markdown(
        f'<p style="font-size: 0.85rem; color: #666; margin-bottom: 0.5rem;">Run: {run_datetime}</p>',
        unsafe_allow_html=True,
    )

    artifacts = ArtifactService.list_artifacts(session, run_id)
    if not artifacts:
        st.warning("No artifacts found for this run.")
        return

    health = ArtifactService.check_run_health(session, run_id)
    status = health.get("status")
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
    module_map = {}
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
    for module, stats in sorted(module_map.items()):
        table_data.append({
            "Module": module,
            "Charts": stats["charts"],
            "Data Files": stats["data"],
            "Last Updated": stats["last"] if stats["last"] else "N/A"
        })
    
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
        unsafe_allow_html=True
    )
    
    with st.container():
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=min(400, 50 + len(df) * 35),  # Dynamic height based on rows, max 400px
        )

    st.divider()
    st.subheader("Export")
    export_mode = st.radio(
        "Export Options",
        [
            "All",
            "Module",
            "Speaker",
            "Charts Only",
            "Data Only",
            "Custom Selection",
        ],
    )
    selected_artifacts = artifacts
    if export_mode == "Module":
        module_options = sorted({a.module for a in artifacts if a.module})
        module_choice = st.selectbox("Module", module_options)
        selected_artifacts = [a for a in artifacts if a.module == module_choice]
    elif export_mode == "Speaker":
        speaker_options = sorted({a.speaker for a in artifacts if a.speaker})
        speaker_choice = st.selectbox("Speaker", speaker_options)
        selected_artifacts = [a for a in artifacts if a.speaker == speaker_choice]
    elif export_mode == "Charts Only":
        selected_artifacts = [a for a in artifacts if a.kind.startswith("chart")]
    elif export_mode == "Data Only":
        selected_artifacts = [a for a in artifacts if a.kind.startswith("data")]
    elif export_mode == "Custom Selection":
        options = {a.id: a.rel_path for a in artifacts}
        chosen = st.multiselect(
            "Artifacts", list(options.keys()), format_func=options.get
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
        confirm_large = st.checkbox("I understand this may take time.")
    if total_bytes > 2 * 1024 * 1024 * 1024:
        st.error("Export exceeds 2GB hard cap.")
        return

    if st.button("Create Export", disabled=not confirm_large):
        export_path = ArtifactService.zip_artifacts(
            session, run_id, [a.id for a in selected_artifacts]
        )
        if export_path:
            try:
                payload = ArtifactService.read_for_download(export_path)
                st.download_button(
                    "Download Export",
                    data=payload,
                    file_name=export_path.name,
                )
            except Exception as exc:
                st.error(f"Export failed: {exc}")
