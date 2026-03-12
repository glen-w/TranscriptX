"""
Audio Merge page — merge multiple audio files into one MP3.

Layout:
    1. File selection and order   — multiselect to choose; move-up/down to order
    2. Output options             — filename, output dir, backup, overwrite
    3. Run and result             — progress stages, playback on success
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import streamlit as st

from transcriptx.app.controllers.merge_controller import MergeController
from transcriptx.app.models.requests import MergeRequest
from transcriptx.app.progress import make_initial_snapshot
from transcriptx.core.utils.file_rename import extract_date_prefix
from transcriptx.core.utils.paths import RECORDINGS_DIR, RECORDINGS_IMPORTS_DIR
from transcriptx.web.components.progress_panel import (
    MERGE_SNAPSHOT_KEY,
    StreamlitProgressCallback,
    render_progress_panel,
)
from transcriptx.web.services.recordings_service import RecordingsService

# ---------------------------------------------------------------------------
# Session-state key constants
# ---------------------------------------------------------------------------
_KEY_ORDERED_PATHS = "audio_merge_ordered_paths"  # list[str] — the merge order
_KEY_RUN_IN_PROGRESS = "audio_merge_run_in_progress"
_KEY_RESULT = "audio_merge_result"

# Always four stages in the progress snapshot
_STAGE_COUNT = 4


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------


def render_audio_merge_page() -> None:
    """Render the Audio Merge page."""
    st.markdown(
        '<div class="main-header">🔗 Audio Merge</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Merge multiple audio files into a single MP3. "
        "Various formats are supported (WAV, MP3, OGG, M4A, FLAC, AAC, WMA)."
    )

    # Upload area — same as Audio Prep; saved to RECORDINGS_IMPORTS_DIR
    uploaded_list = st.file_uploader(
        "Upload audio file(s)",
        type=["mp3", "wav", "m4a", "flac", "ogg", "aac"],
        accept_multiple_files=True,
        help="Uploaded files are saved to the recordings imports folder and appear in the list below.",
        key="audio_merge_uploader",
    )
    if uploaded_list:
        saved_paths: List[Path] = []
        for uploaded in uploaded_list:
            saved_path = RecordingsService.save_uploaded_file(uploaded)
            saved_paths.append(saved_path)
        if len(saved_paths) == 1:
            st.success(
                f"Saved to `{saved_paths[0].relative_to(RECORDINGS_IMPORTS_DIR)}`"
            )
        else:
            st.success(
                f"Saved {len(saved_paths)} files to `{RECORDINGS_IMPORTS_DIR.name}/`"
            )
        RecordingsService.list_recordings.clear()  # type: ignore[attr-defined]

    recordings = RecordingsService.list_recordings(RECORDINGS_DIR)
    if RECORDINGS_IMPORTS_DIR != RECORDINGS_DIR / "imports":
        imports_files = RecordingsService.list_recordings(RECORDINGS_IMPORTS_DIR)
        seen = {p.resolve() for p in recordings}
        for p in imports_files:
            if p.resolve() not in seen:
                recordings.append(p)
        recordings.sort(key=lambda p: p.name)

    if not recordings:
        st.info(
            f"No audio files found in `{RECORDINGS_DIR}`. "
            "Upload a file above or add files to the recordings directory."
        )
        return

    _render_section_1(recordings)


# ---------------------------------------------------------------------------
# Section 1 — File selection and order
# ---------------------------------------------------------------------------


def _render_section_1(recordings: List[Path]) -> None:
    st.subheader("1. Select and order files")
    st.caption(
        "Choose files with the selector below, then use **↑ Move up** / **↓ Move down** "
        "to set the exact merge order. The first file in the list also determines the "
        "output filename date prefix."
    )

    def _label(p: Path) -> str:
        try:
            return str(p.relative_to(RECORDINGS_DIR))
        except ValueError:
            return p.name

    all_labels = {str(p): _label(p) for p in recordings}
    all_paths_str = [str(p) for p in recordings]

    # --- sync ordered list with available recordings ---
    ordered: List[str] = st.session_state.get(_KEY_ORDERED_PATHS, [])
    # Remove any paths that no longer exist in recordings
    ordered = [p for p in ordered if p in all_paths_str]
    st.session_state[_KEY_ORDERED_PATHS] = ordered

    # Multiselect reflects the currently ordered set
    selected_labels = [all_labels[p] for p in ordered if p in all_labels]
    new_selection_labels = st.multiselect(
        "Choose files to merge",
        options=[_label(p) for p in recordings],
        default=selected_labels,
        key="audio_merge_multiselect",
        help="Select 2 or more files. Adjust order with the buttons below.",
    )

    # Resolve labels back to paths (label → path, first match)
    label_to_path = {_label(p): str(p) for p in recordings}
    new_selection_paths = [
        label_to_path[lbl] for lbl in new_selection_labels if lbl in label_to_path
    ]

    # Sync: add newly selected paths to end, remove deselected
    current_set = set(ordered)
    new_set = set(new_selection_paths)
    # Remove deselected
    merged_order = [p for p in ordered if p in new_set]
    # Add newly selected (preserving insertion order)
    for p in new_selection_paths:
        if p not in current_set:
            merged_order.append(p)
    st.session_state[_KEY_ORDERED_PATHS] = merged_order

    if not merged_order:
        st.info("Select at least 2 files above to continue.")
        return

    # --- show ordered list with move-up / move-down ---
    st.markdown("**Merge order** (top = first in output):")
    for i, path_str in enumerate(merged_order):
        col_label, col_up, col_down = st.columns([8, 1, 1])
        with col_label:
            label = all_labels.get(path_str, path_str)
            meta_str = ""
            try:
                meta = RecordingsService.get_audio_metadata(Path(path_str))
                dur = RecordingsService.format_duration(meta.duration_sec)
                meta_str = f"  `{meta.format}` · {dur} · {meta.file_size_mb} MB"
            except Exception:
                pass
            st.markdown(f"{i + 1}. **{label}**{meta_str}")
        with col_up:
            if i > 0 and st.button("↑", key=f"merge_up_{i}", help="Move up"):
                merged_order[i], merged_order[i - 1] = (
                    merged_order[i - 1],
                    merged_order[i],
                )
                st.session_state[_KEY_ORDERED_PATHS] = merged_order
                st.rerun()
        with col_down:
            if i < len(merged_order) - 1 and st.button(
                "↓", key=f"merge_down_{i}", help="Move down"
            ):
                merged_order[i], merged_order[i + 1] = (
                    merged_order[i + 1],
                    merged_order[i],
                )
                st.session_state[_KEY_ORDERED_PATHS] = merged_order
                st.rerun()

    if len(merged_order) < 2:
        st.warning("Select at least 2 files to merge.")
        return

    # Duplicate guard (shouldn't happen via UI, but protect the workflow)
    if len(set(merged_order)) < len(merged_order):
        st.error("Duplicate files detected in the list. Please remove duplicates.")
        return

    _render_section_2([Path(p) for p in merged_order])


# ---------------------------------------------------------------------------
# Section 2 — Output options
# ---------------------------------------------------------------------------


def _render_section_2(ordered_paths: List[Path]) -> None:
    st.subheader("2. Output options")

    date_prefix = extract_date_prefix(ordered_paths[0])
    default_filename = f"{date_prefix}merged.mp3" if date_prefix else "merged.mp3"

    output_filename = st.text_input(
        "Output filename",
        value=st.session_state.get("audio_merge_output_filename", default_filename),
        key="audio_merge_output_filename",
        help=(
            "Date prefix is taken from the first file in the merge order. "
            "The .mp3 extension is added automatically if omitted."
        ),
    )

    col_backup, col_overwrite = st.columns(2)
    with col_backup:
        backup_wavs = st.checkbox(
            "Backup originals to storage before merging",
            value=st.session_state.get("audio_merge_backup", True),
            key="audio_merge_backup",
            help=(
                "Copies each source file to the WAV storage directory "
                "and deletes the original before merging."
            ),
        )
    with col_overwrite:
        overwrite = st.checkbox(
            "Overwrite output if it already exists",
            value=st.session_state.get("audio_merge_overwrite", False),
            key="audio_merge_overwrite",
        )

    _render_section_3(
        ordered_paths=ordered_paths,
        output_filename=output_filename,
        backup_wavs=backup_wavs,
        overwrite=overwrite,
    )


# ---------------------------------------------------------------------------
# Section 3 — Run and result
# ---------------------------------------------------------------------------


def _render_section_3(
    ordered_paths: List[Path],
    output_filename: str,
    backup_wavs: bool,
    overwrite: bool,
) -> None:
    st.subheader("3. Run")

    # If in progress show panel and return
    if st.session_state.get(_KEY_RUN_IN_PROGRESS, False):
        snapshot = st.session_state.get(MERGE_SNAPSHOT_KEY)
        if snapshot is not None:
            render_progress_panel(snapshot)
        else:
            st.info("Merging…")
        return

    last_result = st.session_state.get(_KEY_RESULT)
    if last_result is not None:
        _render_result(last_result)
        with st.expander("Merge again", expanded=False):
            _render_run_button(ordered_paths, output_filename, backup_wavs, overwrite)
    else:
        _render_run_button(ordered_paths, output_filename, backup_wavs, overwrite)


def _render_run_button(
    ordered_paths: List[Path],
    output_filename: str,
    backup_wavs: bool,
    overwrite: bool,
) -> None:
    n = len(ordered_paths)
    label = f"▶ Merge {n} files"

    if st.button(label, type="primary", key="audio_merge_run"):
        request = MergeRequest(
            file_paths=ordered_paths,
            output_dir=Path(RECORDINGS_DIR),
            output_filename=output_filename or None,
            backup_wavs=backup_wavs,
            overwrite=overwrite,
        )

        st.session_state[MERGE_SNAPSHOT_KEY] = make_initial_snapshot(total=_STAGE_COUNT)
        st.session_state[_KEY_RUN_IN_PROGRESS] = True
        # Clear previous result so it doesn't show during the run
        st.session_state.pop(_KEY_RESULT, None)

        progress = StreamlitProgressCallback(MERGE_SNAPSHOT_KEY)
        ctrl = MergeController()

        with st.status(f"Merging {n} files…", expanded=True) as status_widget:
            try:
                result = ctrl.run_merge(request, progress=progress)
            except Exception as exc:
                from transcriptx.app.models.results import MergeResult

                result = MergeResult(success=False, errors=[str(exc)])
            finally:
                st.session_state[_KEY_RUN_IN_PROGRESS] = False

            if result.success:
                status_widget.update(label="✓ Merge complete", state="complete")
            else:
                status_widget.update(label="✗ Merge failed", state="error")

        st.session_state[_KEY_RESULT] = result
        st.rerun()


def _render_result(result: object) -> None:
    """Render the outcome of the last merge run."""
    from transcriptx.app.models.results import MergeResult

    r: MergeResult = result  # type: ignore[assignment]

    if r.success:
        st.success(
            f"Merged {r.files_merged} file(s) into **{r.output_path.name}**"
            if r.output_path
            else f"Merged {r.files_merged} file(s) successfully."
        )

        if r.warnings:
            for w in r.warnings:
                st.warning(w)

        if r.output_path and r.output_path.exists():
            st.markdown("**Listen to merged output:**")
            try:
                audio_bytes = r.output_path.read_bytes()
                st.audio(audio_bytes, format="audio/mpeg")
            except Exception as exc:
                st.caption(f"Playback unavailable: {exc}")
            st.caption(f"`{r.output_path}`")
    else:
        st.error("Merge failed.")
        for err in r.errors:
            st.error(err)
        if r.warnings:
            for w in r.warnings:
                st.warning(w)
