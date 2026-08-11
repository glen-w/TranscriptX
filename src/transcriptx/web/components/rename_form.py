"""
Shared Streamlit rename forms for transcript and audio-linked workflows.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from transcriptx.core.utils.rename.date_prefix import suggest_rename_base_name
from transcriptx.web.services.rename_service import RenameResult, RenameService

_DEFAULT_CAPTION = (
    "Renames the transcript and linked working-copy audio, when present. "
    "Archival originals stay stable."
)
_DEFAULT_HELP = (
    "Use letters, numbers, spaces, hyphens, and underscores. Do not include extension."
)


def _prefill_date_prefix_enabled() -> bool:
    try:
        from transcriptx.core.utils.config_provider import get_config

        cfg = get_config()
        return bool(
            getattr(
                getattr(cfg, "input", None), "prefill_rename_with_date_prefix", True
            )
        )
    except Exception:
        return True


def _path_fingerprint(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def sticky_suggested_name_keys(form_key: str) -> tuple[str, str, str]:
    """Return (bound_path_key, target_input_key, last_suggestion_key)."""
    return (
        f"{form_key}__bound_path",
        f"{form_key}__target",
        f"{form_key}__last_suggestion",
    )


def clear_rename_form_session_keys(form_key: str, session_state=None) -> None:
    """Drop sticky form bindings (call after rename or transcript switch cleanup)."""
    ss = st.session_state if session_state is None else session_state
    for key in sticky_suggested_name_keys(form_key):
        ss.pop(key, None)


def bind_suggested_rename_name(
    transcript_path: Path | str,
    *,
    form_key: str,
    date_prefix_prefill: bool = False,
) -> str:
    """Recompute suggested name only when the selected transcript path changes.

    Returns the current suggested/default name bound into session state.
    """
    path = Path(transcript_path)
    bound_key, target_key, suggestion_key = sticky_suggested_name_keys(form_key)
    fingerprint = _path_fingerprint(path)
    if st.session_state.get(bound_key) != fingerprint:
        if date_prefix_prefill:
            suggested = suggest_rename_base_name(
                path, prefill_with_date_prefix=_prefill_date_prefix_enabled()
            )
        else:
            suggested = path.stem
        st.session_state[bound_key] = fingerprint
        st.session_state[suggestion_key] = suggested
        st.session_state[target_key] = suggested
    return str(st.session_state.get(suggestion_key) or path.stem)


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
    date_prefix_prefill: bool = False,
) -> None:
    """Render rename form for a transcript path; calls RenameService on submit."""
    path = Path(transcript_path)
    if not path.exists():
        return

    current_name = path.stem
    bind_suggested_rename_name(
        path, form_key=form_key, date_prefix_prefill=date_prefix_prefill
    )
    _, target_key, _ = sticky_suggested_name_keys(form_key)

    _render_rename_heading(title, as_subheader=as_subheader, show_heading=show_heading)
    if caption:
        st.caption(caption)
    if date_prefix_prefill:
        st.caption(
            "Suggested name is date-prefixed (YYMMDD_) from the recording or "
            "transcript when available."
        )
    with st.form(form_key, clear_on_submit=False):
        st.text_input("Current file name", value=current_name, disabled=True)
        target = st.text_input(
            "New file name",
            key=target_key,
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
