"""
Shared Streamlit rename forms for transcript and audio-linked workflows.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from transcriptx.web.services.rename_service import RenameResult, RenameService

_DEFAULT_CAPTION = (
    "Keeps transcript JSON and linked audio filename in sync using the same base name."
)
_DEFAULT_HELP = (
    "Use letters, numbers, spaces, hyphens, and underscores. Do not include extension."
)


def _render_rename_heading(
    title: str, *, as_subheader: bool, show_heading: bool
) -> None:
    if not show_heading or not title:
        return
    if as_subheader:
        st.subheader(title)
    else:
        st.markdown(f"#### {title}")


def _handle_rename_submit(
    result: RenameResult,
    *,
    success_message: str,
    library_transcripts: list | None,
    on_success: Callable[[RenameResult], None] | None,
) -> None:
    if not result.ok:
        st.error(result.message)
        return
    RenameService.after_rename(
        result,
        library_transcripts=library_transcripts,
        extra_session_patch=on_success,
    )
    st.success(success_message)
    st.rerun()


def render_transcript_rename_form(
    transcript_path: Path | str,
    *,
    form_key: str,
    title: str = "Rename transcript + linked audio",
    caption: str = _DEFAULT_CAPTION,
    submit_label: str = "Rename transcript and audio",
    as_subheader: bool = False,
    show_heading: bool = True,
    library_transcripts: list | None = None,
    on_success: Callable[[RenameResult], None] | None = None,
) -> None:
    """Render rename form for a transcript path; calls RenameService on submit."""
    path = Path(transcript_path)
    if not path.exists():
        return

    current_name = path.stem
    _render_rename_heading(title, as_subheader=as_subheader, show_heading=show_heading)
    if caption:
        st.caption(caption)
    with st.form(form_key, clear_on_submit=False):
        st.text_input("Current file name", value=current_name, disabled=True)
        target = st.text_input(
            "New file name",
            value=current_name,
            help=_DEFAULT_HELP,
        )
        submitted = st.form_submit_button(submit_label)
    if not submitted:
        return

    result = RenameService.rename_transcript_and_audio(path, target)
    _handle_rename_submit(
        result,
        success_message=(
            f"Renamed `{result.old_base_name}` to `{result.new_base_name}`."
        ),
        library_transcripts=library_transcripts,
        on_success=on_success,
    )


def render_audio_linked_rename_form(
    audio_path: Path | str,
    *,
    form_key: str,
    title: str = "Rename linked transcript + audio",
    caption: str = (
        "This action requires a linked transcript and keeps transcript/audio "
        "filenames aligned."
    ),
    submit_label: str = "Rename linked files",
    as_subheader: bool = False,
    show_heading: bool = True,
    on_success: Callable[[RenameResult], None] | None = None,
) -> None:
    """Render rename form starting from a linked audio recording path."""
    path = Path(audio_path)
    if not path.exists():
        return

    current_name = path.stem
    _render_rename_heading(title, as_subheader=as_subheader, show_heading=show_heading)
    if caption:
        st.caption(caption)
    with st.form(form_key, clear_on_submit=False):
        st.text_input("Current file name", value=current_name, disabled=True)
        target = st.text_input(
            "New file name",
            value=current_name,
            help="Do not include extension. Linked transcript and audio will share this name.",
        )
        submitted = st.form_submit_button(submit_label)
    if not submitted:
        return

    result = RenameService.rename_from_audio(path, target)
    _handle_rename_submit(
        result,
        success_message=(
            f"Renamed `{result.old_base_name}` to `{result.new_base_name}`."
        ),
        library_transcripts=None,
        on_success=on_success,
    )
