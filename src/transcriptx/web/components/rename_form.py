"""
Shared Streamlit rename forms for transcript and audio-linked workflows.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from transcriptx.core.utils.rename.date_prefix import suggest_rename_base_name
from transcriptx.core.utils.rename.smart_name import (
    SmartRenameSuggestion,
    append_token_to_name,
    smart_rename_suggests_in_rename_workflow,
    suggest_smart_rename_base_name,
)
from transcriptx.core.utils.rename.title_stem import (
    propose_dated_title,
    stem_looks_like_natural_language_title,
    title_word_bubbles,
)
from transcriptx.web import icons as ic
from transcriptx.web.services.rename_service import RenameResult, RenameService
from transcriptx.web.components.info_tooltip import widget_help

_DEFAULT_CAPTION = (
    "Renames the transcript and linked working-copy audio, when present. "
    "Archival originals stay stable."
)
_DEFAULT_HELP = (
    "Use letters, numbers, spaces, hyphens, and underscores. Do not include extension."
)


def _input_rename_settings() -> tuple[str, str, bool]:
    try:
        from transcriptx.core.utils.config_provider import get_config

        cfg = get_config()
        input_cfg = getattr(cfg, "input", None)
        mode = str(
            getattr(input_cfg, "smart_rename_mode", "suggest_import")
            or "suggest_import"
        )
        pattern = str(
            getattr(input_cfg, "smart_rename_pattern", "{yymmdd}_{period}_{n}")
            or "{yymmdd}_{period}_{n}"
        )
        legacy = bool(getattr(input_cfg, "prefill_rename_with_date_prefix", True))
        return mode, pattern, legacy
    except Exception:
        return "suggest_import", "{yymmdd}_{period}_{n}", True


def _prefill_date_prefix_enabled() -> bool:
    _, _, legacy = _input_rename_settings()
    return legacy


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


def sticky_smart_rename_keys(form_key: str) -> tuple[str, str]:
    """Return (bubbles_key, date_root_key) for smart rename UI state."""
    return (f"{form_key}__bubbles", f"{form_key}__date_root")


def sticky_content_rename_keys(form_key: str) -> tuple[str, str, str]:
    """Return (options_key, pick_key, status_key) for content rename suggestions."""
    return (
        f"{form_key}__content_options",
        f"{form_key}__content_pick",
        f"{form_key}__content_status",
    )


def sticky_nl_title_reuse_key(form_key: str) -> str:
    return f"{form_key}__nl_title_reuse"


def _rename_content_suggestions_mode() -> str:
    try:
        from transcriptx.core.utils.config_provider import get_config

        cfg = get_config()
        return str(
            getattr(getattr(cfg, "input", None), "rename_content_suggestions", "off")
            or "off"
        )
    except Exception:
        return "off"


def clear_rename_form_session_keys(form_key: str, session_state=None) -> None:
    """Drop sticky form bindings (call after rename or transcript switch cleanup)."""
    ss = st.session_state if session_state is None else session_state
    for key in sticky_suggested_name_keys(form_key):
        ss.pop(key, None)
    for key in sticky_smart_rename_keys(form_key):
        ss.pop(key, None)
    for key in sticky_content_rename_keys(form_key):
        ss.pop(key, None)
    ss.pop(sticky_nl_title_reuse_key(form_key), None)


def _smart_prefill_from_suggestion(
    path: Path,
    suggestion: SmartRenameSuggestion,
) -> tuple[str, list[str], str, bool]:
    """Return (suggested_name, bubbles, date_root, nl_title_reuse)."""
    stem = path.stem
    if suggestion.date_root and stem_looks_like_natural_language_title(stem):
        return (
            propose_dated_title(suggestion.date_root, stem),
            list(title_word_bubbles(stem)),
            suggestion.date_root,
            True,
        )
    if suggestion.date_root:
        return (
            suggestion.date_root,
            list(suggestion.token_bubbles),
            suggestion.date_root,
            False,
        )
    if suggestion.full:
        return (
            suggestion.full,
            list(suggestion.token_bubbles),
            suggestion.date_root,
            False,
        )
    return (stem, [], "", False)


def _store_content_suggestion_result(
    path: Path,
    form_key: str,
    content_result,
    *,
    session_state,
) -> None:
    options_key, pick_key, status_key = sticky_content_rename_keys(form_key)
    bubbles_key, date_root_key = sticky_smart_rename_keys(form_key)
    _, target_key, suggestion_key = sticky_suggested_name_keys(form_key)
    nl_key = sticky_nl_title_reuse_key(form_key)

    labels: list[str] = []
    label_to_stem: dict[str, str] = {}
    for opt in content_result.options:
        label = f"{opt.stem} — {opt.basis}, {opt.confidence}"
        labels.append(label)
        label_to_stem[label] = opt.stem
    session_state[options_key] = label_to_stem
    session_state[status_key] = content_result.status
    session_state[pick_key] = labels[0] if labels else ""

    if content_result.prefill:
        session_state[suggestion_key] = content_result.prefill
        session_state[target_key] = content_result.prefill
        if stem_looks_like_natural_language_title(path.stem):
            session_state[bubbles_key] = list(title_word_bubbles(path.stem))
            session_state[nl_key] = True
        else:
            session_state.pop(bubbles_key, None)
            session_state.pop(date_root_key, None)
            session_state.pop(nl_key, None)


def _cb_suggest_rename_names(transcript_path: str, form_key: str) -> None:
    from transcriptx.core.utils.rename.suggestions import suggest_rename_stems

    path = Path(transcript_path)
    result = suggest_rename_stems(path, force_refresh=True, on_demand=True)
    _store_content_suggestion_result(
        path, form_key, result, session_state=st.session_state
    )


def _rename_suggest_button_label() -> str:
    try:
        from transcriptx.core.utils.config import get_config

        cfg = get_config().llm
        llm_on = bool(cfg.enabled and (cfg.provider or "").strip().lower() == "ollama")
    except Exception:
        llm_on = False
    return (
        "Suggest names (transcript + LLM)"
        if llm_on
        else "Suggest names (transcript only)"
    )


def _resolve_smart_suggestion(
    path: Path,
    *,
    enable_smart: bool,
) -> SmartRenameSuggestion | None:
    if not enable_smart:
        return None
    mode, pattern, _ = _input_rename_settings()
    if not smart_rename_suggests_in_rename_workflow(mode):
        return None
    try:
        return suggest_smart_rename_base_name(path, mode=mode, pattern=pattern)
    except Exception:
        return None


def bind_suggested_rename_name(
    transcript_path: Path | str,
    *,
    form_key: str,
    date_prefix_prefill: bool = False,
    enable_smart: bool | None = None,
) -> str:
    """Recompute suggested name only when the selected transcript path changes.

    When smart rename applies, prefills the **date root** (e.g. ``260810_``)
    and stores clickable token bubbles in session state. Otherwise uses legacy
    date-prefix-plus-stem behaviour when ``date_prefix_prefill`` is true.

    Returns the current suggested/default name bound into session state.
    """
    path = Path(transcript_path)
    bound_key, target_key, suggestion_key = sticky_suggested_name_keys(form_key)
    bubbles_key, date_root_key = sticky_smart_rename_keys(form_key)
    fingerprint = _path_fingerprint(path)
    options_key, pick_key, status_key = sticky_content_rename_keys(form_key)
    nl_key = sticky_nl_title_reuse_key(form_key)
    if st.session_state.get(bound_key) != fingerprint:
        mode, _pattern, legacy = _input_rename_settings()
        content_mode = _rename_content_suggestions_mode()
        if content_mode == "auto":
            from transcriptx.core.utils.rename.suggestions import suggest_rename_stems

            content_result = suggest_rename_stems(path)
            labels: list[str] = []
            label_to_stem: dict[str, str] = {}
            for opt in content_result.options:
                label = f"{opt.stem} — {opt.basis}, {opt.confidence}"
                labels.append(label)
                label_to_stem[label] = opt.stem
            st.session_state[options_key] = label_to_stem
            st.session_state[status_key] = content_result.status
            if content_result.prefill:
                suggested = content_result.prefill
                if stem_looks_like_natural_language_title(path.stem):
                    st.session_state[bubbles_key] = list(title_word_bubbles(path.stem))
                    st.session_state[nl_key] = True
                else:
                    st.session_state[bubbles_key] = []
                    st.session_state[date_root_key] = ""
                    st.session_state.pop(nl_key, None)
            else:
                use_smart = (
                    enable_smart
                    if enable_smart is not None
                    else (
                        date_prefix_prefill
                        and smart_rename_suggests_in_rename_workflow(mode)
                    )
                )
                suggestion = _resolve_smart_suggestion(
                    path, enable_smart=bool(use_smart)
                )
                if suggestion is not None:
                    suggested, bubbles, date_root, nl_reuse = (
                        _smart_prefill_from_suggestion(path, suggestion)
                    )
                    st.session_state[bubbles_key] = bubbles
                    st.session_state[date_root_key] = date_root
                    st.session_state[nl_key] = nl_reuse
                elif date_prefix_prefill:
                    suggested = suggest_rename_base_name(
                        path,
                        prefill_with_date_prefix=_prefill_date_prefix_enabled()
                        and legacy,
                        smart_rename_mode="off",
                    )
                else:
                    suggested = path.stem
            st.session_state[pick_key] = labels[0] if labels else ""
            st.session_state[bound_key] = fingerprint
            st.session_state[suggestion_key] = suggested
            st.session_state[target_key] = suggested
            return str(st.session_state.get(suggestion_key) or path.stem)

        use_smart = (
            enable_smart
            if enable_smart is not None
            else (
                date_prefix_prefill and smart_rename_suggests_in_rename_workflow(mode)
            )
        )
        st.session_state.pop(options_key, None)
        st.session_state.pop(pick_key, None)
        st.session_state.pop(status_key, None)
        suggestion = _resolve_smart_suggestion(path, enable_smart=bool(use_smart))
        if suggestion is not None:
            suggested, bubbles, date_root, nl_reuse = _smart_prefill_from_suggestion(
                path, suggestion
            )
            st.session_state[bubbles_key] = bubbles
            st.session_state[date_root_key] = date_root
            st.session_state[nl_key] = nl_reuse
        else:
            st.session_state.pop(bubbles_key, None)
            st.session_state.pop(date_root_key, None)
            st.session_state.pop(nl_key, None)
            if date_prefix_prefill:
                suggested = suggest_rename_base_name(
                    path,
                    prefill_with_date_prefix=_prefill_date_prefix_enabled() and legacy,
                    smart_rename_mode="off",
                )
            else:
                suggested = path.stem
        st.session_state[bound_key] = fingerprint
        st.session_state[suggestion_key] = suggested
        st.session_state[target_key] = suggested
    return str(st.session_state.get(suggestion_key) or path.stem)


def _render_content_suggestion_dropdown(form_key: str) -> None:
    options_key, pick_key, status_key = sticky_content_rename_keys(form_key)
    _, target_key, _ = sticky_suggested_name_keys(form_key)
    label_to_stem = st.session_state.get(options_key) or {}
    if not label_to_stem:
        return
    status = str(st.session_state.get(status_key) or "")
    if status:
        st.caption(status)
    labels = list(label_to_stem.keys())
    current_pick = st.session_state.get(pick_key)
    index = labels.index(current_pick) if current_pick in labels else 0
    chosen = st.selectbox(
        "Suggested names",
        labels,
        index=index,
        key=f"{form_key}__content_select",
    )
    if chosen != current_pick:
        st.session_state[pick_key] = chosen
        stem = label_to_stem.get(chosen)
        if stem:
            st.session_state[target_key] = stem
        st.rerun()


def _render_token_bubbles(form_key: str) -> None:
    bubbles_key, _ = sticky_smart_rename_keys(form_key)
    _, target_key, _ = sticky_suggested_name_keys(form_key)
    bubbles = st.session_state.get(bubbles_key) or []
    if not bubbles:
        return
    st.caption("Click a token to append it to the new file name.")
    cols = st.columns(min(len(bubbles), 6))
    for idx, token in enumerate(bubbles):
        col = cols[idx % len(cols)]
        with col:
            if st.button(
                token,
                key=f"{form_key}__bubble_{idx}_{token}",
                use_container_width=True,
            ):
                current = str(st.session_state.get(target_key) or "")
                st.session_state[target_key] = append_token_to_name(current, token)
                st.rerun()


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
    enable_smart: bool | None = None,
) -> None:
    """Render rename form for a transcript path; calls RenameService on submit."""
    path = Path(transcript_path)
    if not path.exists():
        return

    current_name = path.stem
    bind_suggested_rename_name(
        path,
        form_key=form_key,
        date_prefix_prefill=date_prefix_prefill,
        enable_smart=enable_smart,
    )
    _, target_key, _ = sticky_suggested_name_keys(form_key)
    bubbles_key, _ = sticky_smart_rename_keys(form_key)
    has_bubbles = bool(st.session_state.get(bubbles_key))
    nl_reuse = bool(st.session_state.get(sticky_nl_title_reuse_key(form_key)))

    _render_rename_heading(title, as_subheader=as_subheader, show_heading=show_heading)
    if caption:
        st.caption(caption)
    if nl_reuse:
        st.caption(
            "Recording date is prefilled from the filename when available; the "
            "rest is your existing title with spaces replaced by underscores."
        )
    elif has_bubbles:
        st.caption(
            "Suggested date root is prefilled from the recording filename when "
            "available. Use the token buttons to build a custom title."
        )
    elif date_prefix_prefill:
        st.caption(
            "Suggested name is date-prefixed (YYMMDD_) from the recording or "
            "transcript when available."
        )

    # Bubbles live outside the form so clicks can update the text field immediately.
    _render_token_bubbles(form_key)
    st.button(
        _rename_suggest_button_label(),
        key=f"{form_key}__suggest_rename",
        icon=ic.SEARCH,
        help=widget_help(
            "Build rename candidates from the transcript and optional local LLM. "
            "Pick a suggestion below — nothing is renamed until you submit Rename. "
            "Uses the `rename_suggestions` model from Settings → Models when LLM is on."
        ),
        on_click=_cb_suggest_rename_names,
        args=(str(path), form_key),
    )
    if _rename_content_suggestions_mode() == "auto" or (
        st.session_state.get(sticky_content_rename_keys(form_key)[0])
    ):
        _render_content_suggestion_dropdown(form_key)

    with st.form(form_key, clear_on_submit=False):
        st.text_input("Current file name", value=current_name, disabled=True)
        target = st.text_input(
            "New file name",
            key=target_key,
            help=widget_help(_DEFAULT_HELP),
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
            help=widget_help(
                "Do not include extension. Linked transcript and working-copy audio will share this name."
            ),
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
