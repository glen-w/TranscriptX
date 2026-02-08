"""
File list page for TranscriptX Studio.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.web.services import RunIndex, SubjectService


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

    files = [p for p in run_dir.rglob("*") if p.is_file()]
    files = sorted(files)
    
    if not files:
        st.info("No files found in this run directory.")
        return
    
    total_files = len(files)
    st.metric("Total Files", total_files)
    
    # Search/filter
    search_term = st.text_input("🔍 Search files", key="file_search")
    if search_term:
        files = [f for f in files if search_term.lower() in f.name.lower() or search_term.lower() in str(f.relative_to(run_dir)).lower()]
        st.caption(f"Showing {len(files)} of {total_files} files")
    
    st.divider()
    
    # Display files with download/open buttons
    for path in files:
        rel = path.relative_to(run_dir).as_posix()
        
        # Create columns for file info and action button
        col1, col2 = st.columns([4, 1])
        
        with col1:
            # Display file path with icon based on extension
            file_ext = path.suffix.lower()
            icon = "📄"
            if file_ext in [".json"]:
                icon = "📋"
            elif file_ext in [".txt", ".md"]:
                icon = "📝"
            elif file_ext in [".png", ".jpg", ".jpeg", ".gif", ".svg"]:
                icon = "🖼️"
            elif file_ext in [".csv"]:
                icon = "📊"
            elif file_ext in [".wav", ".mp3", ".m4a", ".flac"]:
                icon = "🎵"
            elif file_ext in [".html", ".htm"]:
                icon = "🌐"
            
            st.markdown(f"{icon} **{rel}**")
            file_size = path.stat().st_size
            size_str = f"{file_size:,} bytes"
            if file_size > 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            if file_size > 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            st.caption(f"Size: {size_str}")
        
        with col2:
            # Download button that allows opening the file
            try:
                with open(path, "rb") as f:
                    file_data = f.read()
                    st.download_button(
                        label="📥 Open",
                        data=file_data,
                        file_name=path.name,
                        mime=_get_mime_type(path),
                        key=f"download_{path.as_posix().replace('/', '_').replace(' ', '_')}",
                        width='stretch',
                    )
            except Exception as e:
                st.error(f"Error: {str(e)[:50]}")
        
        st.divider()


def _get_mime_type(path: Path) -> str:
    """Get MIME type based on file extension."""
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
