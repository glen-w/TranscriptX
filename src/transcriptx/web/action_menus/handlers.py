"""Closed action handler registry: availability, render, post_render."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from transcriptx.app.library_delete import (
    delete_managed_library_transcript,
    is_managed_library_transcript,
)
from transcriptx.web import icons as ic
from transcriptx.web.action_menus.catalog import help_for, icon_for, label_for
from transcriptx.web.action_menus.context import ActionContext, ContextCapabilities
from transcriptx.web.action_menus.ids import (
    ActionDisplay,
    ActionId,
    NavStyle,
    SectionId,
)
from transcriptx.web.action_menus.services import (
    PAGE_ARTIFACTS,
    PAGE_CHARTS,
    PAGE_CORRECTIONS,
    PAGE_INSIGHTS,
    PAGE_LIBRARY,
    PAGE_OVERVIEW,
    PAGE_RUN_ANALYSIS,
    PAGE_SPEAKER_ID,
    PAGE_TRANSCRIPT,
    go_rename,
    navigate_with_identity,
    prepare_run_export,
    render_export_residuals,
)
from transcriptx.web.cache_helpers import clear_transcript_listing_caches
from transcriptx.web.components.action_links import render_action_link
from transcriptx.web.navigation import apply_library_rename_navigation
from transcriptx.web.state import (
    LIBRARY_SELECTED_TRANSCRIPT_PATH,
    LIBRARY_TABLE_EPOCH_KEY,
    PAGE_KEY,
    SUBJECT_ID_KEY,
    apply_subject_context,
    set_page_flash,
    try_page_toast,
)


@dataclass(frozen=True)
class ActionHandler:
    is_available: Callable[[ActionContext, ContextCapabilities], bool]
    render: Callable[..., None]
    post_render: Callable[[ActionContext, str], None] | None = None


def _nav(ctx: ActionContext, page: str) -> None:
    navigate_with_identity(ctx.identity, page)


def _available_run_scoped(_ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.has_valid_run


def _available_insights(_ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.has_completed_compatible_run


def _available_export(_ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.export_supported


def _available_rename(_ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.rename_supported


def _available_transcript_file(ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return ctx.identity.subject_type == "transcript" and caps.has_transcript_path


def _available_open_transcript(ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return _available_transcript_file(ctx, caps) and caps.has_valid_run


def _available_corrections(ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.corrections_workspace_available


def _available_correct_in_viewer(ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.corrections_workspace_available and caps.has_valid_run


def _available_open_library(ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return ctx.identity.subject_type == "transcript" and (
        caps.has_transcript_path or bool(ctx.identity.subject_id)
    )


def _available_workflow(ctx: ActionContext, caps: ContextCapabilities) -> bool:
    if ctx.identity.subject_type == "group":
        return True
    return caps.has_transcript_path or bool(ctx.identity.subject_id)


def _button(
    ctx: ActionContext,
    *,
    action: ActionId,
    section: SectionId,
    key: str,
    on_activate: Callable[[], None],
    display: str = ActionDisplay.BOTH.value,
) -> None:
    label = label_for(action, section)
    icon = icon_for(action)
    help_text = help_for(action)
    if ctx.nav_style == NavStyle.ON_CLICK:
        # Mutate session state only. Outside fragments Streamlit already
        # schedules a full-app rerun after on_click; calling rerun from the
        # callback is a no-op and surfaces a client warning.
        # Fragment-hosted strips must use NavStyle.CLICK_RERUN instead.
        render_action_link(
            label,
            key=key,
            icon=icon,
            help=help_text,
            display=display,
            on_click=on_activate,
        )
    else:
        if render_action_link(
            label, key=key, icon=icon, help=help_text, display=display
        ):
            on_activate()
            st.rerun()


def _render_open(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    _button(
        ctx,
        action=ActionId.OPEN,
        section=section,
        key=key,
        display=display,
        on_activate=lambda: _nav(ctx, PAGE_OVERVIEW),
    )


def _render_charts(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    _button(
        ctx,
        action=ActionId.CHARTS,
        section=section,
        key=key,
        display=display,
        on_activate=lambda: _nav(ctx, PAGE_CHARTS),
    )


def _render_artifacts(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    _button(
        ctx,
        action=ActionId.ARTIFACTS,
        section=section,
        key=key,
        display=display,
        on_activate=lambda: _nav(ctx, PAGE_ARTIFACTS),
    )


def _render_insights(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    _button(
        ctx,
        action=ActionId.INSIGHTS,
        section=section,
        key=key,
        display=display,
        on_activate=lambda: _nav(ctx, PAGE_INSIGHTS),
    )


def _render_transcript(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    _button(
        ctx,
        action=ActionId.OPEN_TRANSCRIPT,
        section=section,
        key=key,
        display=display,
        on_activate=lambda: _nav(ctx, PAGE_TRANSCRIPT),
    )


def _render_corrections(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    _button(
        ctx,
        action=ActionId.CORRECTIONS,
        section=section,
        key=key,
        display=display,
        on_activate=lambda: _nav(ctx, PAGE_CORRECTIONS),
    )


def _render_correct_in_viewer(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    def _go() -> None:
        st.session_state["transcript_viewer_correct_mode"] = True
        _nav(ctx, PAGE_TRANSCRIPT)

    _button(
        ctx,
        action=ActionId.CORRECT_IN_VIEWER,
        section=section,
        key=key,
        display=display,
        on_activate=_go,
    )


def _render_run_analysis(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    _button(
        ctx,
        action=ActionId.RUN_ANALYSIS,
        section=section,
        key=key,
        display=display,
        on_activate=lambda: _nav(ctx, PAGE_RUN_ANALYSIS),
    )


def _render_speaker_id(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    _button(
        ctx,
        action=ActionId.RUN_SPEAKER_ID,
        section=section,
        key=key,
        display=display,
        on_activate=lambda: _nav(ctx, PAGE_SPEAKER_ID),
    )


def _render_open_library(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    def _go() -> None:
        if ctx.identity.transcript_path is not None:
            apply_library_rename_navigation(
                st.session_state, ctx.identity.transcript_path
            )
        else:
            navigate_with_identity(ctx.identity, PAGE_LIBRARY)
            return
        st.session_state[PAGE_KEY] = PAGE_LIBRARY

    _button(
        ctx,
        action=ActionId.OPEN_LIBRARY,
        section=section,
        key=key,
        display=display,
        on_activate=_go,
    )


def _render_rename(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    _button(
        ctx,
        action=ActionId.RENAME,
        section=section,
        key=key,
        display=display,
        on_activate=lambda: go_rename(ctx.identity),
    )


def _render_export(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    # Export uses click (not on_click) so prepare runs in the same script path.
    label = label_for(ActionId.EXPORT_ZIP, section)
    if render_action_link(
        label,
        key=key,
        icon=icon_for(ActionId.EXPORT_ZIP),
        help=help_for(ActionId.EXPORT_ZIP),
        display=display,
    ):
        prepare_run_export(ctx.identity)


def _clear_session_after_library_delete(path: Path) -> None:
    ss = st.session_state
    ss.pop(LIBRARY_SELECTED_TRANSCRIPT_PATH, None)
    ss[LIBRARY_TABLE_EPOCH_KEY] = int(ss.get(LIBRARY_TABLE_EPOCH_KEY) or 0) + 1
    subject = ss.get(SUBJECT_ID_KEY)
    if subject and str(subject) == path.stem:
        apply_subject_context(ss, subject_type=None, subject_id=None, run_id=None)


@st.dialog("Delete transcript?")
def _confirm_delete_transcript_dialog(path_str: str) -> None:
    path = Path(path_str)
    st.markdown(f"Permanently delete **`{path.name}`**?")
    st.caption(
        "Removes this managed transcript and its companions (speaker map, "
        "import sidecar, readable copy). Linked recordings and analysis runs "
        "are kept. This cannot be undone."
    )
    col_ok, col_cancel = st.columns(2)
    with col_ok:
        if st.button(
            "Delete",
            type="primary",
            icon=icon_for(ActionId.DELETE),
            key="lib_confirm_delete_transcript",
        ):
            result = delete_managed_library_transcript(path)
            if not result.ok:
                for err in result.errors:
                    st.error(err)
                for warn in result.warnings:
                    st.warning(warn)
                return
            _clear_session_after_library_delete(path)
            clear_transcript_listing_caches()
            extras: list[str] = []
            if result.emptied_groups:
                extras.append(
                    "Groups with no remaining members were left unchanged: "
                    + ", ".join(result.emptied_groups)
                )
            if result.dangling_speaker_links:
                extras.append(
                    f"{result.dangling_speaker_links} speaker-profile link(s) still "
                    "point at this transcript."
                )
            extras.extend(result.warnings)
            msg = f"Deleted {path.name}."
            if extras:
                msg = msg + " " + " ".join(extras)
            kind = "warning" if extras else "success"
            set_page_flash(kind, msg)
            try_page_toast(msg)
            st.rerun()
    with col_cancel:
        if st.button("Cancel", icon=ic.CANCEL, key="lib_cancel_delete_transcript"):
            st.rerun()


def _render_delete(
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str = ActionDisplay.BOTH.value,
) -> None:
    # Dialog must open on the same script path (click return), not on_click.
    path = ctx.identity.transcript_path
    disabled = path is None or not is_managed_library_transcript(path)
    if render_action_link(
        label_for(ActionId.DELETE, section),
        key=key,
        icon=icon_for(ActionId.DELETE),
        help=help_for(ActionId.DELETE),
        display=display,
        disabled=disabled,
    ):
        if path is not None:
            _confirm_delete_transcript_dialog(str(path))


def _post_export(ctx: ActionContext, download_key: str) -> None:
    render_export_residuals(ctx.identity, download_key=download_key)


HANDLERS: dict[ActionId, ActionHandler] = {
    ActionId.OPEN: ActionHandler(_available_run_scoped, _render_open),
    ActionId.OPEN_LIBRARY: ActionHandler(_available_open_library, _render_open_library),
    ActionId.OPEN_TRANSCRIPT: ActionHandler(
        _available_open_transcript, _render_transcript
    ),
    ActionId.CHARTS: ActionHandler(_available_run_scoped, _render_charts),
    ActionId.ARTIFACTS: ActionHandler(_available_run_scoped, _render_artifacts),
    ActionId.INSIGHTS: ActionHandler(_available_insights, _render_insights),
    ActionId.EXPORT_ZIP: ActionHandler(_available_export, _render_export, _post_export),
    ActionId.RENAME: ActionHandler(_available_rename, _render_rename),
    ActionId.DELETE: ActionHandler(_available_transcript_file, _render_delete),
    ActionId.RUN_SPEAKER_ID: ActionHandler(_available_workflow, _render_speaker_id),
    ActionId.RUN_ANALYSIS: ActionHandler(_available_workflow, _render_run_analysis),
    ActionId.CORRECTIONS: ActionHandler(_available_corrections, _render_corrections),
    ActionId.CORRECT_IN_VIEWER: ActionHandler(
        _available_correct_in_viewer, _render_correct_in_viewer
    ),
}


def is_action_available(
    action: ActionId, ctx: ActionContext, caps: ContextCapabilities
) -> bool:
    handler = HANDLERS.get(action)
    if handler is None:
        return False
    return handler.is_available(ctx, caps)


def render_action(
    action: ActionId,
    ctx: ActionContext,
    *,
    section: SectionId,
    key: str,
    display: str | None = None,
) -> None:
    if display is None:
        from transcriptx.web.action_menus.prefs import (
            get_cached_runtime_prefs,
            resolve_action_display,
        )

        display = resolve_action_display(get_cached_runtime_prefs(), section).value
    HANDLERS[action].render(ctx, section=section, key=key, display=display)


def post_render_action(
    action: ActionId, ctx: ActionContext, *, download_key: str
) -> None:
    handler = HANDLERS.get(action)
    if handler and handler.post_render:
        handler.post_render(ctx, download_key)
