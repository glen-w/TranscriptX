"""
Shared Streamlit rename forms for transcript and audio-linked workflows.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from transcriptx.web.services.rename_service import RenameResult, RenameService

_DEFAULT_CAPTION = (
    "Renames the transcript and linked working-copy audio, when present. "
    "Archival originals stay stable."
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
    # Committed (complete or partial): refresh session onto the new path
    if result.transaction_committed:
        RenameService.after_rename(
            result,
            library_transcripts=library_transcripts,
            extra_session_patch=on_success,
        )
        if result.ok:
            st.success(success_message)
        else:
            st.warning(
                "Transcript rename committed, but some follow-up work is incomplete "
                "and can be repaired."
            )
            st.warning(result.message)
            if result.operation_id:
                st.code(result.operation_id, language=None)
            if result.errors:
                for err in result.errors:
                    label = getattr(err, "message", err)
                    phase = getattr(err, "phase", "")
                    code = getattr(err, "code", "")
                    st.caption(
                        f"{phase}:{code} — {label}" if phase or code else str(label)
                    )
        st.rerun()
        return

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
    title: str = "Rename transcript (and linked working-copy audio when present)",
    caption: str = _DEFAULT_CAPTION,
    submit_label: str = "Rename",
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
    phrase = RenameService._audio_outcome_phrase(
        result.audio_kind, result.audio_renamed
    )
    _handle_rename_submit(
        result,
        success_message=(
            f"Renamed `{result.old_base_name}` to `{result.new_base_name}` "
            f"({phrase})."
        ),
        library_transcripts=library_transcripts,
        on_success=on_success,
    )


def render_audio_linked_rename_form(
    audio_path: Path | str,
    *,
    form_key: str,
    title: str = "Rename linked transcript + working-copy audio",
    caption: str = (
        "Requires a linked transcript. Renames the transcript and linked "
        "working-copy audio when present; archival originals stay stable."
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
            help="Do not include extension. Linked transcript and working-copy audio will share this name.",
        )
        submitted = st.form_submit_button(submit_label)
    if not submitted:
        return

    result = RenameService.rename_from_audio(path, target)
    phrase = RenameService._audio_outcome_phrase(
        result.audio_kind, result.audio_renamed
    )
    _handle_rename_submit(
        result,
        success_message=(
            f"Renamed `{result.old_base_name}` to `{result.new_base_name}` "
            f"({phrase})."
        ),
        library_transcripts=None,
        on_success=on_success,
    )
