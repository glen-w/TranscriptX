"""
File list page for TranscriptX Studio.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st

from transcriptx.web.services import ArtifactService, RunIndex, SubjectService


@st.cache_data(ttl=30, show_spinner=False)
def _cached_run_files(run_root_str: str) -> list:
    run_dir = Path(run_root_str)
    if not run_dir.exists():
        return []
    files = [p for p in run_dir.rglob("*") if p.is_file()]
    return sorted(files)


def _format_size(size_bytes: int) -> str:
    if size_bytes > 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes > 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes:,} bytes"


def _file_icon(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in [".json"]:
        return "📋"
    if ext in [".txt", ".md"]:
        return "📝"
    if ext in [".png", ".jpg", ".jpeg", ".gif", ".svg"]:
        return "🖼️"
    if ext in [".csv"]:
        return "📊"
    if ext in [".wav", ".mp3", ".m4a", ".flac"]:
        return "🎵"
    if ext in [".html", ".htm"]:
        return "🌐"
    return "📄"


def _get_mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    mime_types = {
        ".json": "application/json",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".html": "text/html",
        ".htm": "text/html",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".md": "text/markdown",
    }
    return mime_types.get(ext, "application/octet-stream")


def _render_file_row(run_dir: Path, path: Path, key_suffix: str) -> None:
    rel = path.relative_to(run_dir).as_posix()
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"{_file_icon(path)} **{rel}**")
        try:
            size = path.stat().st_size
            st.caption(f"Size: {_format_size(size)}")
        except OSError:
            st.caption("Size: —")
    with col2:
        try:
            with open(path, "rb") as f:
                file_data = f.read()
            st.download_button(
                label="📥 Download",
                data=file_data,
                file_name=path.name,
                mime=_get_mime_type(path),
                key=f"download_{key_suffix}",
                width="stretch",
            )
        except Exception as e:
            st.caption(f"Error: {str(e)[:40]}")


def render_explorer() -> None:
    subject = SubjectService.resolve_current_subject(st.session_state)
    run_id = st.session_state.get("run_id")
    if not subject or not run_id:
        st.info("Select a subject and run to view files.")
        return
    run_dir = RunIndex.get_run_root(
        subject.scope,
        run_id,
        subject_id=subject.subject_id,
    )
    if not run_dir.exists():
        st.error("Run directory not found.")
        return

    st.subheader("File List")
    st.caption("Browse and open files from the run directory.")

    all_files = _cached_run_files(str(run_dir))
    # Exclude internal paths from "all files" for display
    display_files = [
        p
        for p in all_files
        if not p.relative_to(run_dir).as_posix().startswith(".transcriptx/")
    ]

    artifacts = ArtifactService.list_artifacts(run_dir)
    by_module: dict[str, list] = defaultdict(list)
    artifact_paths: set[str] = set()
    for a in artifacts:
        by_module[a.module or "Other"].append(a)
        artifact_paths.add(a.rel_path)

    # Orphan files (on disk but not in manifest)
    orphan_paths = [
        p
        for p in display_files
        if p.relative_to(run_dir).as_posix() not in artifact_paths
        and p.name not in ("manifest.json", "run_results.json")
    ]

    total_files = len(display_files)
    st.metric("Total Files", total_files)

    # Search/filter (applies to which file rows are shown below)
    search_term = st.text_input("🔍 Search files", key="file_search")
    search_lower = search_term.lower() if search_term else None

    def _matches_search(path: Path) -> bool:
        if not search_lower:
            return True
        rel = path.relative_to(run_dir).as_posix()
        return search_lower in path.name.lower() or search_lower in rel.lower()

    if search_term:
        st.caption(f"Filtering by: «{search_term}»")

    # Charts: by module and by extension
    if artifacts or display_files:
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            if by_module:
                mod_counts = pd.DataFrame(
                    [
                        {"Module": k, "Files": len(v)}
                        for k, v in sorted(by_module.items())
                    ]
                )
                st.bar_chart(mod_counts.set_index("Module"), height=200)
        with col_chart2:
            ext_counts: dict[str, int] = defaultdict(int)
            for p in display_files:
                ext = p.suffix.lower() or "(none)"
                ext_counts[ext] += 1
            if ext_counts:
                ext_df = pd.DataFrame(
                    [
                        {"Extension": k, "Count": v}
                        for k, v in sorted(ext_counts.items())
                    ]
                )
                st.bar_chart(ext_df.set_index("Extension"), height=200)

    st.divider()

    # Sections per module (from artifacts)
    for module_name in sorted(by_module.keys()):
        module_artifacts = by_module[module_name]
        shown = [a for a in module_artifacts if _matches_search(Path(a.rel_path))]
        if not shown and search_lower:
            continue
        st.subheader(module_name, anchor=module_name.lower().replace(" ", "-"))
        st.caption(f"{len(shown)} of {len(module_artifacts)} file(s)")
        for art in module_artifacts:
            full_path = ArtifactService._resolve_safe_path(run_dir, art.rel_path)
            if full_path is None or not full_path.exists():
                st.caption(f"Missing: {art.rel_path}")
                continue
            if not _matches_search(full_path):
                continue
            _render_file_row(
                run_dir,
                full_path,
                f"mod_{module_name}_{art.id}".replace("/", "_").replace(" ", "_"),
            )
        st.divider()

    # Other files (orphans)
    if orphan_paths:
        shown_orphans = [p for p in sorted(orphan_paths) if _matches_search(p)]
        if shown_orphans or not search_lower:
            st.subheader("Other files", anchor="other-files")
            st.caption("Files in run directory not listed in manifest.")
            for path in sorted(orphan_paths):
                if not _matches_search(path):
                    continue
                rel = path.relative_to(run_dir).as_posix()
                _render_file_row(
                    run_dir, path, f"orphan_{rel.replace('/', '_').replace(' ', '_')}"
                )
            st.divider()

    if not artifacts and not orphan_paths and not display_files:
        st.info("No files found in this run directory.")
