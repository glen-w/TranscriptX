"""Closed action handler registry: availability, render, post_render."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import streamlit as st

from transcriptx.web.action_menus.catalog import help_for, icon_for, label_for
from transcriptx.web.action_menus.context import ActionContext, ContextCapabilities
from transcriptx.web.action_menus.ids import ActionId, NavStyle, SectionId
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
from transcriptx.web.components.action_links import render_action_link
from transcriptx.web.navigation import apply_library_rename_navigation
from transcriptx.web.state import PAGE_KEY


@dataclass(frozen=True)
class ActionHandler:
    is_available: Callable[[ActionContext, ContextCapabilities], bool]
    render: Callable[..., None]
    post_render: Callable[[ActionContext, str], None] | None = None


def _nav(ctx: ActionContext, page: str) -> None:
    navigate_with_identity(ctx.identity, page)


def _available_open(ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.has_transcript_path or caps.has_valid_run


def _available_run_scoped(_ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.has_valid_run


def _available_insights(_ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.has_completed_compatible_run


def _available_export(_ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.export_supported


def _available_rename(_ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.rename_supported


def _available_transcript(ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return ctx.identity.subject_type == "transcript" and caps.has_transcript_path


def _available_corrections(ctx: ActionContext, caps: ContextCapabilities) -> bool:
    return caps.corrections_workspace_available


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
            label, key=key, icon=icon, help=help_text, on_click=on_activate
        )
    else:
        if render_action_link(label, key=key, icon=icon, help=help_text):
            on_activate()
            st.rerun()


def _render_open(ctx: ActionContext, *, section: SectionId, key: str) -> None:
    _button(
        ctx,
        action=ActionId.OPEN,
        section=section,
        key=key,
        on_activate=lambda: _nav(ctx, PAGE_OVERVIEW),
    )


def _render_charts(ctx: ActionContext, *, section: SectionId, key: str) -> None:
    _button(
        ctx,
        action=ActionId.CHARTS,
        section=section,
        key=key,
        on_activate=lambda: _nav(ctx, PAGE_CHARTS),
    )


def _render_artifacts(ctx: ActionContext, *, section: SectionId, key: str) -> None:
    _button(
        ctx,
        action=ActionId.ARTIFACTS,
        section=section,
        key=key,
        on_activate=lambda: _nav(ctx, PAGE_ARTIFACTS),
    )


def _render_insights(ctx: ActionContext, *, section: SectionId, key: str) -> None:
    _button(
        ctx,
        action=ActionId.INSIGHTS,
        section=section,
        key=key,
        on_activate=lambda: _nav(ctx, PAGE_INSIGHTS),
    )


def _render_transcript(ctx: ActionContext, *, section: SectionId, key: str) -> None:
    _button(
        ctx,
        action=ActionId.OPEN_TRANSCRIPT,
        section=section,
        key=key,
        on_activate=lambda: _nav(ctx, PAGE_TRANSCRIPT),
    )


def _render_corrections(ctx: ActionContext, *, section: SectionId, key: str) -> None:
    _button(
        ctx,
        action=ActionId.CORRECTIONS,
        section=section,
        key=key,
        on_activate=lambda: _nav(ctx, PAGE_CORRECTIONS),
    )


def _render_run_analysis(ctx: ActionContext, *, section: SectionId, key: str) -> None:
    _button(
        ctx,
        action=ActionId.RUN_ANALYSIS,
        section=section,
        key=key,
        on_activate=lambda: _nav(ctx, PAGE_RUN_ANALYSIS),
    )


def _render_speaker_id(ctx: ActionContext, *, section: SectionId, key: str) -> None:
    _button(
        ctx,
        action=ActionId.RUN_SPEAKER_ID,
        section=section,
        key=key,
        on_activate=lambda: _nav(ctx, PAGE_SPEAKER_ID),
    )


def _render_open_library(ctx: ActionContext, *, section: SectionId, key: str) -> None:
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
        on_activate=_go,
    )


def _render_rename(ctx: ActionContext, *, section: SectionId, key: str) -> None:
    _button(
        ctx,
        action=ActionId.RENAME,
        section=section,
        key=key,
        on_activate=lambda: go_rename(ctx.identity),
    )


def _render_export(ctx: ActionContext, *, section: SectionId, key: str) -> None:
    # Export uses click (not on_click) so prepare runs in the same script path.
    label = label_for(ActionId.EXPORT_ZIP, section)
    if render_action_link(
        label,
        key=key,
        icon=icon_for(ActionId.EXPORT_ZIP),
        help=help_for(ActionId.EXPORT_ZIP),
    ):
        prepare_run_export(ctx.identity)


def _post_export(ctx: ActionContext, download_key: str) -> None:
    render_export_residuals(ctx.identity, download_key=download_key)


HANDLERS: dict[ActionId, ActionHandler] = {
    ActionId.OPEN: ActionHandler(_available_open, _render_open),
    ActionId.OPEN_LIBRARY: ActionHandler(_available_open_library, _render_open_library),
    ActionId.OPEN_TRANSCRIPT: ActionHandler(_available_transcript, _render_transcript),
    ActionId.CHARTS: ActionHandler(_available_run_scoped, _render_charts),
    ActionId.ARTIFACTS: ActionHandler(_available_run_scoped, _render_artifacts),
    ActionId.INSIGHTS: ActionHandler(_available_insights, _render_insights),
    ActionId.EXPORT_ZIP: ActionHandler(_available_export, _render_export, _post_export),
    ActionId.RENAME: ActionHandler(_available_rename, _render_rename),
    ActionId.RUN_SPEAKER_ID: ActionHandler(_available_workflow, _render_speaker_id),
    ActionId.RUN_ANALYSIS: ActionHandler(_available_workflow, _render_run_analysis),
    ActionId.CORRECTIONS: ActionHandler(_available_corrections, _render_corrections),
}


def is_action_available(
    action: ActionId, ctx: ActionContext, caps: ContextCapabilities
) -> bool:
    handler = HANDLERS.get(action)
    if handler is None:
        return False
    return handler.is_available(ctx, caps)


def render_action(
    action: ActionId, ctx: ActionContext, *, section: SectionId, key: str
) -> None:
    HANDLERS[action].render(ctx, section=section, key=key)


def post_render_action(
    action: ActionId, ctx: ActionContext, *, download_key: str
) -> None:
    handler = HANDLERS.get(action)
    if handler and handler.post_render:
        handler.post_render(ctx, download_key)
