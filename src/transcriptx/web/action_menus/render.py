"""Render configured action strips."""

from __future__ import annotations

import hashlib

import streamlit as st

from transcriptx.web.action_menus.context import ActionContext
from transcriptx.web.action_menus.handlers import post_render_action, render_action
from transcriptx.web.action_menus.ids import ActionId, SectionId
from transcriptx.web.action_menus.prefs import InterfaceMenuPrefs
from transcriptx.web.action_menus.resolve import resolve_section_actions


def action_widget_key(
    *,
    instance_prefix: str,
    section: SectionId,
    widget_identity: str,
    action: ActionId,
) -> str:
    digest = hashlib.sha1(
        f"{instance_prefix}|{section.value}|{widget_identity}|{action.value}".encode()
    ).hexdigest()[:12]
    return f"{instance_prefix}__{section.value}__{action.value}__{digest}"


def render_configured_actions(
    section: SectionId,
    ctx: ActionContext,
    *,
    prefs: InterfaceMenuPrefs | None = None,
) -> list[ActionId]:
    """Resolve and render the action strip. Returns resolved IDs (may be empty)."""
    actions = resolve_section_actions(section, ctx, prefs=prefs)
    if not actions:
        return []

    cols = st.columns(len(actions), gap="small")
    for col, action in zip(cols, actions):
        key = action_widget_key(
            instance_prefix=ctx.instance_prefix,
            section=section,
            widget_identity=ctx.widget_identity,
            action=action,
        )
        with col:
            render_action(action, ctx, section=section, key=key)

    if ActionId.EXPORT_ZIP in actions:
        dl_key = action_widget_key(
            instance_prefix=ctx.instance_prefix,
            section=section,
            widget_identity=ctx.widget_identity,
            action=ActionId.EXPORT_ZIP,
        ) + "_dl"
        post_render_action(ActionId.EXPORT_ZIP, ctx, download_key=dl_key)

    return actions
