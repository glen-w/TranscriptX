"""Merge panel — concatenate split recordings into one MP3."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.app.controllers.merge_controller import MergeController
from transcriptx.app.models.requests import MergeRequest
from transcriptx.app.models.results import MergeResult
from transcriptx.app.progress import make_initial_snapshot
from transcriptx.core.audio.linked_transcripts import (
    delete_linked_transcripts_for_audio,
    find_transcripts_for_audio,
)
from transcriptx.core.audio.merge_profiles import MergeSourceProfile
from transcriptx.core.audio.serial_groups import (
    SerialGroup,
    detect_merge_groups,
    partition_dismissed_serial_groups,
)
from transcriptx.core.audio.utils import get_audio_duration
from transcriptx.core.utils.paths import RECORDINGS_DIR, RECORDINGS_IMPORTS_DIR
from transcriptx.core.utils.rename.date_prefix import extract_date_prefix
from transcriptx.web.components.progress_panel import (
    MERGE_SNAPSHOT_KEY,
    StreamlitProgressCallback,
    render_progress_panel,
)
from transcriptx.web.components.rename_form import render_audio_linked_rename_form
from transcriptx.web.navigation import (
    MERGE_ORDERED_PATHS_KEY,
    navigate_to_tools_tab,
    navigate_to_transcribe_with_paths,
)
from transcriptx.web.services.recordings_service import RecordingsService
from transcriptx.web.ui.tools.merge_profiles_editor import render_merge_profiles_editor
from transcriptx.web.ui.tools.shared import (
    recordings_path_label,
    render_empty_recordings_hint,
    render_upload_and_refresh,
)
from transcriptx.web.components.info_tooltip import widget_help
from transcriptx.web.state import set_page_flash, try_page_toast

_KEY_ORDERED_PATHS = MERGE_ORDERED_PATHS_KEY
_KEY_HIDDEN_SERIAL = "audio_merge_hidden_serial_keys"
_KEY_RUN_IN_PROGRESS = "audio_merge_run_in_progress"
_KEY_RESULT = "audio_merge_result"
_KEY_AUTO_RESULTS = "audio_merge_auto_results"
_STAGE_COUNT = 4

# Browsers typically allow only ~6–8 concurrent media fetches per origin.
# Eager st.audio() for every part leaves later players stuck at 0:00 / 0:00.
_AUDIO_MIME_BY_SUFFIX = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}


def _audio_mime_for_path(path: Path) -> str:
    return _AUDIO_MIME_BY_SUFFIX.get(path.suffix.lower(), "audio/mpeg")


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _path_is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False


def recording_is_deletable(path: Path) -> bool:
    """True when *path* is a file under recordings or recordings imports."""
    if not path.is_file():
        return False
    return _path_is_under(path, Path(RECORDINGS_DIR)) or _path_is_under(
        path, Path(RECORDINGS_IMPORTS_DIR)
    )


def delete_merge_recording(path: Path) -> tuple[bool, int, list[str]]:
    """Delete a merge-panel recording and linked transcripts.

    Returns ``(audio_deleted, transcripts_deleted, errors)``.
    """
    if not recording_is_deletable(path):
        return (
            False,
            0,
            ["This file is not a managed recording and cannot be deleted here."],
        )
    transcripts_deleted, warnings = delete_linked_transcripts_for_audio(path)
    errors = list(warnings)
    try:
        path.unlink()
    except OSError as exc:
        errors.append(f"Could not delete {path.name}: {exc}")
        return False, transcripts_deleted, errors
    return True, transcripts_deleted, errors


def drop_recording_from_merge_session(session: dict, path: Path) -> None:
    """Remove *path* from the manual-merge order list if present."""
    ordered = session.get(_KEY_ORDERED_PATHS, [])
    if not isinstance(ordered, list):
        return
    path_str = str(path)
    session[_KEY_ORDERED_PATHS] = [item for item in ordered if str(item) != path_str]


@st.dialog("Delete recording?")
def _confirm_delete_recording_dialog(path_str: str) -> None:
    path = Path(path_str)
    st.markdown(f"Permanently delete **`{path.name}`**?")
    st.caption("This cannot be undone.")
    try:
        linked = find_transcripts_for_audio(path)
    except Exception:
        linked = []
    if linked:
        st.caption(f"Also deletes {len(linked)} linked transcript(s).")

    col_ok, col_cancel = st.columns(2)
    with col_ok:
        if st.button(
            "Delete",
            type="primary",
            icon=ic.DELETE,
            key="audio_merge_confirm_delete",
        ):
            ok, tx_count, errors = delete_merge_recording(path)
            if not ok:
                for err in errors:
                    st.error(err)
                return
            drop_recording_from_merge_session(st.session_state, path)
            RecordingsService.list_recordings.clear()  # type: ignore[attr-defined]
            msg = f"Deleted {path.name}."
            if tx_count:
                msg = f"Deleted {path.name} and {tx_count} linked transcript(s)."
            set_page_flash("success", msg)
            try_page_toast(msg)
            st.rerun()
    with col_cancel:
        if st.button("Cancel", icon=ic.CANCEL, key="audio_merge_cancel_delete"):
            st.rerun()


def _render_delete_recording_button(path: Path, *, widget_key: str) -> None:
    if st.button(
        "",
        key=widget_key,
        icon=ic.DELETE,
        help=widget_help("Delete this recording from disk."),
        disabled=not recording_is_deletable(path),
    ):
        _confirm_delete_recording_dialog(str(path))


def hidden_serial_keys_from_session(session: dict) -> list[str]:
    """Return dismissed serial-group keys stored on the Streamlit session."""
    raw = session.get(_KEY_HIDDEN_SERIAL, [])
    if not isinstance(raw, list):
        return []
    return [str(key) for key in raw]


def hide_serial_group_in_session(session: dict, key: str) -> None:
    keys = hidden_serial_keys_from_session(session)
    if key not in keys:
        keys.append(key)
    session[_KEY_HIDDEN_SERIAL] = keys


def restore_serial_group_in_session(session: dict, key: str) -> None:
    session[_KEY_HIDDEN_SERIAL] = [
        existing
        for existing in hidden_serial_keys_from_session(session)
        if existing != key
    ]


def render_auto_merge_panel(*, deps_ready: bool = True) -> None:
    """Render the Auto-merge tool tab."""
    st.caption(
        "Detect split recordings and merge each group into a single MP3. "
        "Supports WAV, MP3, OGG, M4A, FLAC, AAC, and WMA. "
        "Preprocessing is optional and off by default."
    )

    profiles = render_merge_profiles_editor()

    recordings = render_upload_and_refresh(uploader_key="audio_merge_uploader")
    if not recordings:
        render_empty_recordings_hint()
        return

    options = _render_shared_merge_options(key_prefix="audio_merge_auto")
    _render_detected_serial_groups(
        recordings,
        profiles=profiles,
        deps_ready=deps_ready,
        options=options,
    )


def render_manual_merge_panel(*, deps_ready: bool = True) -> None:
    """Render the Manual merge tool tab."""
    st.caption(
        "Choose files and set merge order manually, then concatenate into one MP3. "
        "Supports WAV, MP3, OGG, M4A, FLAC, AAC, and WMA. "
        "Preprocessing is optional and off by default."
    )

    recordings = render_upload_and_refresh(uploader_key="audio_merge_manual_uploader")
    if not recordings:
        render_empty_recordings_hint()
        return

    options = _render_shared_merge_options(key_prefix="audio_merge_manual")
    _render_section_select(recordings, deps_ready=deps_ready, options=options)


def render_merge_panel(*, deps_ready: bool = True) -> None:
    """Render auto- and manual-merge panels together (legacy entry point)."""
    render_auto_merge_panel(deps_ready=deps_ready)
    render_manual_merge_panel(deps_ready=deps_ready)


def _render_shared_merge_options(*, key_prefix: str) -> dict[str, bool]:
    """Merge flags for one panel. ``key_prefix`` must be unique per Streamlit tab."""
    st.subheader("Merge options")
    col_a, col_b = st.columns(2)
    with col_a:
        backup_wavs = st.checkbox(
            "Backup originals to storage before merging",
            value=bool(st.session_state.get(f"{key_prefix}_backup", True)),
            key=f"{key_prefix}_backup",
            help=widget_help(
                "Copies each source file to the WAV storage directory before merging."
            ),
        )
        apply_preprocessing = st.checkbox(
            "Preprocess files while merging",
            value=bool(st.session_state.get(f"{key_prefix}_preprocess", False)),
            key=f"{key_prefix}_preprocess",
            help=widget_help(
                "Apply current preprocessing defaults before concatenating. Off by default."
            ),
        )
    with col_b:
        overwrite = st.checkbox(
            "Overwrite output if it already exists",
            value=bool(st.session_state.get(f"{key_prefix}_overwrite", False)),
            key=f"{key_prefix}_overwrite",
            help=widget_help("Replace an existing merged file at the output path."),
        )
        delete_originals = st.checkbox(
            "Delete originals once merge is complete",
            value=bool(st.session_state.get(f"{key_prefix}_delete_originals", False)),
            key=f"{key_prefix}_delete_originals",
            help=widget_help(
                "Permanently remove source files and linked part transcripts after success."
            ),
        )
    if delete_originals and not backup_wavs:
        st.warning(
            "Originals will be deleted with no storage backup. "
            "Enable backup above unless you are sure you do not need the parts."
        )
    return {
        "backup_wavs": backup_wavs,
        "overwrite": overwrite,
        "delete_originals": delete_originals,
        "apply_preprocessing": apply_preprocessing,
    }


def _render_merge_file_preview(
    path: Path, *, key_suffix: str, show_player: bool
) -> None:
    """Show a filename, and optionally an inline audio player.

    Callers gate ``show_player`` (typically one checkbox per group) so the page
    does not mount every clip at once. Browsers allow only ~6–8 concurrent media
    fetches per origin; pass the path (not bytes) so hour-long MP3s are not read
    into memory on every rerun.
    """
    col_name, col_delete, col_audio = st.columns(
        [4, 1, 3], vertical_alignment="center"
    )
    with col_name:
        st.text(path.name)
    with col_delete:
        _render_delete_recording_button(
            path, widget_key=f"audio_merge_delete_{key_suffix}"
        )
    with col_audio:
        if not show_player:
            return
        if not path.exists():
            st.caption("File not found")
            return
        try:
            # st.audio has no `key` arg; keyed container keeps multi-file previews distinct.
            with st.container(key=f"audio_merge_preview_{key_suffix}"):
                st.audio(path, format=_audio_mime_for_path(path))
        except Exception as exc:
            st.caption(f"Playback unavailable: {exc}")


def _format_merge_row_meta(path: Path) -> str:
    parts: List[str] = []
    try:
        fmt = path.suffix.lstrip(".").upper() or "?"
        parts.append(f"`{fmt}`")
    except Exception:
        pass
    try:
        dur_sec = get_audio_duration(path)
        if dur_sec is not None and dur_sec >= 0:
            parts.append(RecordingsService.format_duration(dur_sec))
    except Exception:
        pass
    try:
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            parts.append(f"{round(size_mb, 2)} MB")
    except Exception:
        pass
    return "  " + " · ".join(parts) if parts else ""


def _safe_filename_piece(value: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("_", (value or "").strip()).strip("._")
    return cleaned[:80] or "group"


def _group_output_filename(group: SerialGroup) -> str:
    date_prefix = extract_date_prefix(group.ordered_paths[0])
    profile_bit = _safe_filename_piece(group.profile_id or group.profile_name)
    base_bit = _safe_filename_piece(group.base_key)
    stem = f"{profile_bit}_{base_bit}_merged" if profile_bit else f"{base_bit}_merged"
    if date_prefix and not stem.startswith(date_prefix):
        return f"{date_prefix}{stem}.mp3"
    return f"{stem}.mp3"


def _unique_output_filename(desired: str, used: set[str]) -> str:
    name = desired if desired.endswith(".mp3") else f"{desired}.mp3"
    if name not in used and not (Path(RECORDINGS_DIR) / name).exists():
        used.add(name)
        return name
    stem = Path(name).stem
    n = 2
    while True:
        candidate = f"{stem}_{n}.mp3"
        if candidate not in used and not (Path(RECORDINGS_DIR) / candidate).exists():
            used.add(candidate)
            return candidate
        n += 1


def _render_detected_serial_groups(
    recordings: List[Path],
    *,
    profiles: list[MergeSourceProfile],
    deps_ready: bool,
    options: dict[str, bool],
) -> None:
    groups = detect_merge_groups(recordings, profiles=profiles)
    if not groups:
        return

    visible, hidden = partition_dismissed_serial_groups(
        groups, hidden_serial_keys_from_session(st.session_state)
    )
    if not visible and not hidden:
        return

    auto_results = st.session_state.get(_KEY_AUTO_RESULTS)
    if auto_results:
        _render_auto_merge_results(auto_results)

    if visible:
        st.subheader("Detected groups")
        st.caption(
            "These files look like parts of one recording or a burst of voice notes. "
            "Tune grouping under Merge source profiles (draft applies immediately; "
            "Save persists). "
            "Check **Preview clips** on a group to listen (one group at a time works best). "
            "Auto-merge selected groups here, hide false matches, or open "
            "**Manual merge** to pick files and order yourself."
        )
        selected: list[SerialGroup] = []
        for group in visible:
            checked = _render_serial_group_card(group)
            if checked:
                selected.append(group)

        if st.button(
            f"Auto-merge selected groups ({len(selected)})",
            type="primary",
            icon=ic.MERGE,
            key="audio_merge_auto_run",
            disabled=not deps_ready or not selected,
            help=widget_help("Merge each checked group using the Merge options above."),
        ):
            _run_auto_merge(
                selected,
                backup_wavs=options["backup_wavs"],
                overwrite=options["overwrite"],
                delete_originals=options["delete_originals"],
                apply_preprocessing=options["apply_preprocessing"],
            )

    if hidden:
        with st.expander(f"Hidden suggestions ({len(hidden)})", expanded=False):
            st.caption(
                "Hidden for this session. Restore a suggestion if you hid it by mistake."
            )
            for group in hidden:
                col_label, col_restore = st.columns([8, 2])
                with col_label:
                    label = group.profile_name or group.matched_rule
                    st.text(
                        f"{group.base_key} · {len(group.ordered_paths)} files · "
                        f"{label}"
                    )
                with col_restore:
                    if st.button(
                        "Restore",
                        key=f"audio_merge_restore_group_{group.dismissal_key}",
                        icon=ic.RESTORE,
                        help=widget_help("Show this suggestion again."),
                    ):
                        restore_serial_group_in_session(
                            st.session_state, group.dismissal_key
                        )
                        st.rerun()


def _render_serial_group_card(group: SerialGroup) -> bool:
    extension = group.ordered_paths[0].suffix.lower() if group.ordered_paths else ""
    total_duration = 0.0
    duration_known = True
    for path in group.ordered_paths:
        dur = get_audio_duration(path)
        if dur is None:
            duration_known = False
            break
        total_duration += dur

    profile_label = group.profile_name or "Profile"
    with st.container(border=True):
        selected = st.checkbox(
            f"Include in auto-merge · {profile_label}",
            value=True,
            key=f"audio_merge_select_group_{group.dismissal_key}",
        )
        st.markdown(
            f"**{group.base_key}** · {len(group.ordered_paths)} files · "
            f"`{extension}` · {profile_label} · {group.rule_label} · {group.confidence}"
        )
        if duration_known:
            st.caption(
                f"Combined duration: {RecordingsService.format_duration(total_duration)}"
            )
        preview = st.checkbox(
            "Preview clips",
            value=False,
            key=f"audio_merge_preview_group_{group.dismissal_key}",
            help=widget_help(
                "Load players for every file in this group. Prefer one group at "
                "a time — browsers limit concurrent media downloads."
            ),
        )
        for index, path in enumerate(group.ordered_paths):
            _render_merge_file_preview(
                path,
                key_suffix=f"{group.dismissal_key}_{index}",
                show_player=preview,
            )
        for warning in group.warnings:
            st.caption(f"⚠ {warning}")
        col_use, col_hide = st.columns(2)
        with col_use:
            if st.button(
                "Open in Manual merge",
                key=f"audio_merge_use_group_{group.dismissal_key}",
                icon=ic.MERGE,
            ):
                navigate_to_tools_tab(
                    st.session_state,
                    "Manual merge",
                    merge_ordered_paths=[str(p) for p in group.ordered_paths],
                )
                st.rerun()
        with col_hide:
            if st.button(
                "Hide",
                key=f"audio_merge_hide_group_{group.dismissal_key}",
                icon=ic.HIDE,
                help=widget_help(
                    "Hide this suggestion. Use when these files are separate "
                    "sessions, not parts of one recording."
                ),
            ):
                hide_serial_group_in_session(st.session_state, group.dismissal_key)
                st.rerun()
        return selected


def _run_auto_merge(
    groups: list[SerialGroup],
    *,
    backup_wavs: bool,
    overwrite: bool,
    delete_originals: bool,
    apply_preprocessing: bool,
) -> None:
    ctrl = MergeController()
    used_names: set[str] = set()
    results: list[dict] = []
    deleted_paths: set[Path] = set()

    st.session_state[_KEY_RUN_IN_PROGRESS] = True
    st.session_state.pop(_KEY_RESULT, None)
    try:
        with st.status(
            f"Auto-merging {len(groups)} group(s)…", expanded=True
        ) as status_widget:
            for group in groups:
                remaining = [
                    path
                    for path in group.ordered_paths
                    if path not in deleted_paths and path.exists()
                ]
                if len(remaining) < 2:
                    results.append(
                        {
                            "group": group.base_key,
                            "result": MergeResult(
                                success=False,
                                errors=[
                                    "Skipped: fewer than 2 source files remain "
                                    "(earlier delete-originals may have removed them)."
                                ],
                            ),
                        }
                    )
                    continue

                output_name = _unique_output_filename(
                    _group_output_filename(group), used_names
                )
                request = MergeRequest(
                    file_paths=remaining,
                    output_dir=Path(RECORDINGS_DIR),
                    output_filename=output_name,
                    backup_wavs=backup_wavs,
                    overwrite=overwrite,
                    delete_originals=delete_originals,
                    apply_preprocessing=apply_preprocessing,
                )
                try:
                    result = ctrl.run_merge(request)
                except Exception as exc:
                    result = MergeResult(success=False, errors=[str(exc)])
                results.append({"group": group.base_key, "result": result})
                if result.success and delete_originals:
                    for path in remaining:
                        deleted_paths.add(path)
            ok = sum(1 for item in results if item["result"].success)
            status_widget.update(
                label=f"Auto-merge finished ({ok}/{len(results)} succeeded)",
                state="complete" if ok else "error",
            )
    finally:
        st.session_state[_KEY_RUN_IN_PROGRESS] = False

    st.session_state[_KEY_AUTO_RESULTS] = results
    st.rerun()


def _render_auto_merge_results(results: list[dict]) -> None:
    st.subheader("Auto-merge results")
    for item in results:
        result: MergeResult = item["result"]
        label = item.get("group") or "group"
        if result.success:
            name = result.output_path.name if result.output_path else "merged output"
            st.success(f"**{label}** → {name} ({result.files_merged} files)")
            if result.files_deleted or result.transcripts_deleted:
                parts = []
                if result.files_deleted:
                    parts.append(f"{result.files_deleted} original(s)")
                if result.transcripts_deleted:
                    parts.append(f"{result.transcripts_deleted} transcript(s)")
                st.caption("Deleted " + " and ".join(parts) + ".")
            for warning in result.warnings:
                st.warning(warning)
        else:
            st.error(f"**{label}** failed")
            for err in result.errors:
                st.error(err)
    if st.button(
        "Clear auto-merge results", key="audio_merge_clear_auto", icon=ic.CLEAR
    ):
        st.session_state.pop(_KEY_AUTO_RESULTS, None)
        st.rerun()


@st.fragment
def _render_section_select(
    recordings: List[Path],
    *,
    deps_ready: bool,
    options: dict[str, bool],
) -> None:
    st.subheader("1. Select and order files")
    st.caption(
        "Choose files below, then use ↑ / ↓ to set merge order. "
        "The first file also sets the output filename date prefix."
    )

    all_labels = {str(p): recordings_path_label(p) for p in recordings}
    all_paths_str = [str(p) for p in recordings]

    ordered: List[str] = st.session_state.get(_KEY_ORDERED_PATHS, [])
    ordered = [p for p in ordered if p in all_paths_str]
    st.session_state[_KEY_ORDERED_PATHS] = ordered

    selected_labels = [all_labels[p] for p in ordered if p in all_labels]
    new_selection_labels = st.multiselect(
        "Choose files to merge",
        options=[recordings_path_label(p) for p in recordings],
        default=selected_labels,
        key="audio_merge_multiselect",
        help=widget_help(
            "Select 2 or more files. Adjust order with the buttons below."
        ),
    )

    label_to_path = {recordings_path_label(p): str(p) for p in recordings}
    new_selection_paths = [
        label_to_path[lbl] for lbl in new_selection_labels if lbl in label_to_path
    ]

    current_set = set(ordered)
    new_set = set(new_selection_paths)
    merged_order = [p for p in ordered if p in new_set]
    for p in new_selection_paths:
        if p not in current_set:
            merged_order.append(p)
    st.session_state[_KEY_ORDERED_PATHS] = merged_order

    if not merged_order:
        st.info("Select at least 2 files above to continue.")
        return

    st.markdown("**Merge order** (top = first in output):")
    for i, path_str in enumerate(merged_order):
        col_label, col_delete, col_up, col_down = st.columns(
            [7, 1, 1, 1], vertical_alignment="center"
        )
        with col_label:
            label = all_labels.get(path_str, path_str)
            meta_str = _format_merge_row_meta(Path(path_str))
            st.markdown(f"{i + 1}. **{label}**{meta_str}")
        with col_delete:
            _render_delete_recording_button(
                Path(path_str), widget_key=f"audio_merge_delete_order_{i}"
            )
        with col_up:
            if i > 0 and st.button(
                "",
                key=f"merge_up_{i}",
                icon=ic.MOVE_UP,
                help=widget_help("Move up"),
            ):
                merged_order[i], merged_order[i - 1] = (
                    merged_order[i - 1],
                    merged_order[i],
                )
                st.session_state[_KEY_ORDERED_PATHS] = merged_order
                try:
                    st.rerun(scope="fragment")
                except TypeError:
                    st.rerun()
        with col_down:
            if i < len(merged_order) - 1 and st.button(
                "",
                key=f"merge_down_{i}",
                icon=ic.MOVE_DOWN,
                help=widget_help("Move down"),
            ):
                merged_order[i], merged_order[i + 1] = (
                    merged_order[i + 1],
                    merged_order[i],
                )
                st.session_state[_KEY_ORDERED_PATHS] = merged_order
                try:
                    st.rerun(scope="fragment")
                except TypeError:
                    st.rerun()

    _render_rename_section(merged_order, all_labels)

    if len(merged_order) < 2:
        st.warning("Select at least 2 files to merge.")
        return

    if len(set(merged_order)) < len(merged_order):
        st.error("Duplicate files detected in the list. Please remove duplicates.")
        return

    _render_output_and_run(
        [Path(p) for p in merged_order],
        deps_ready=deps_ready,
        options=options,
    )


def _render_rename_section(merged_order: List[str], all_labels: dict[str, str]) -> None:
    with st.expander("Rename linked transcript + audio", expanded=False):
        st.caption(
            "Rename a selected recording together with its linked transcript so "
            "base names match."
        )
        target_audio = st.selectbox(
            "Recording to rename",
            options=merged_order,
            format_func=lambda p: all_labels.get(p, p),
            key="audio_merge_rename_target",
        )
        render_audio_linked_rename_form(
            Path(target_audio),
            form_key="audio_merge_rename_form",
            show_heading=False,
            caption="",
        )


def _render_output_and_run(
    ordered_paths: List[Path],
    *,
    deps_ready: bool,
    options: dict[str, bool],
) -> None:
    st.subheader("2. Output options")

    date_prefix = extract_date_prefix(ordered_paths[0])
    default_filename = f"{date_prefix}merged.mp3" if date_prefix else "merged.mp3"

    output_filename = st.text_input(
        "Output filename",
        value=st.session_state.get("audio_merge_output_filename", default_filename),
        key="audio_merge_output_filename",
        help=widget_help(
            (
                "Date prefix is taken from the first file in the merge order. "
                "The .mp3 extension is added automatically if omitted."
            )
        ),
    )
    st.caption(
        "Backup / overwrite / preprocess / delete-originals use the Merge options above."
    )

    backup_wavs = options["backup_wavs"]
    overwrite = options["overwrite"]
    delete_originals = options["delete_originals"]
    apply_preprocessing = options["apply_preprocessing"]

    st.subheader("3. Run")

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
            _render_run_button(
                ordered_paths,
                output_filename,
                backup_wavs,
                overwrite,
                delete_originals,
                apply_preprocessing,
                deps_ready=deps_ready,
            )
    else:
        _render_run_button(
            ordered_paths,
            output_filename,
            backup_wavs,
            overwrite,
            delete_originals,
            apply_preprocessing,
            deps_ready=deps_ready,
        )


def _render_run_button(
    ordered_paths: List[Path],
    output_filename: str,
    backup_wavs: bool,
    overwrite: bool,
    delete_originals: bool,
    apply_preprocessing: bool,
    *,
    deps_ready: bool,
) -> None:
    n = len(ordered_paths)
    if not deps_ready:
        st.warning("Install ffmpeg and pydub before merging.")

    if st.button(
        f"Merge {n} files",
        type="primary",
        icon=ic.MERGE,
        key="audio_merge_run",
        disabled=not deps_ready,
    ):
        request = MergeRequest(
            file_paths=ordered_paths,
            output_dir=Path(RECORDINGS_DIR),
            output_filename=output_filename or None,
            backup_wavs=backup_wavs,
            overwrite=overwrite,
            delete_originals=delete_originals,
            apply_preprocessing=apply_preprocessing,
        )

        st.session_state[MERGE_SNAPSHOT_KEY] = make_initial_snapshot(total=_STAGE_COUNT)
        st.session_state[_KEY_RUN_IN_PROGRESS] = True
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
    r: MergeResult = result  # type: ignore[assignment]

    if r.success:
        st.success(
            f"Merged {r.files_merged} file(s) into **{r.output_path.name}**"
            if r.output_path
            else f"Merged {r.files_merged} file(s) successfully."
        )
        if r.files_deleted or r.transcripts_deleted:
            parts = []
            if r.files_deleted:
                parts.append(f"{r.files_deleted} original file(s)")
            if r.transcripts_deleted:
                parts.append(f"{r.transcripts_deleted} linked transcript(s)")
            st.caption("Deleted " + " and ".join(parts) + ".")

        if r.warnings:
            for w in r.warnings:
                st.warning(w)

        if r.output_path and r.output_path.exists():
            st.markdown("**Listen to merged output:**")
            try:
                st.audio(r.output_path, format="audio/mpeg")
            except Exception as exc:
                st.caption(f"Playback unavailable: {exc}")
            st.caption(f"`{r.output_path}`")

            col_prep, col_tx = st.columns(2)
            with col_prep:
                if st.button(
                    "Preprocess merged file",
                    key="audio_merge_to_preprocess",
                    icon=ic.GRAPHIC_EQ,
                ):
                    navigate_to_tools_tab(
                        st.session_state,
                        "Preprocessing",
                        preprocess_paths=[r.output_path],
                    )
                    st.rerun()
            with col_tx:
                if st.button(
                    "Open Transcribe Audio",
                    type="primary",
                    icon=ic.TRANSCRIBE,
                    key="audio_merge_transcribe_result",
                ):
                    navigate_to_transcribe_with_paths(st.session_state, [r.output_path])
                    st.rerun()
    else:
        st.error("Merge failed.")
        for err in r.errors:
            st.error(err)
        if r.warnings:
            for w in r.warnings:
                st.warning(w)
