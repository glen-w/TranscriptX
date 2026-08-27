"""Compact tertiary icon-links for navigation and download actions."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal

import streamlit as st
from transcriptx.web import icons as ic
from transcriptx.web.components.info_tooltip import widget_help

# Streamlit exposes widget keys as ``st-key-<key>`` CSS classes; this prefix
# scopes shared action-link styling in shell.py.
ACTION_LINK_KEY_PREFIX = "tx_al_"

# Streamlit rejects a truly empty button label; icon-only uses a nbsp.
_ICON_ONLY_LABEL = "\u00a0"

ActionLinkDisplay = Literal["icon", "text", "both"]


def action_link_key(key: str) -> str:
    if key.startswith(ACTION_LINK_KEY_PREFIX):
        return key
    return f"{ACTION_LINK_KEY_PREFIX}{key}"


def action_link_chrome(
    label: str,
    icon: str | None,
    display: str,
) -> tuple[str, str | None]:
    """Map action name + icon onto Streamlit button label/icon for a display mode.

    ``icon`` → empty (nbsp) label + icon; ``text`` → label and no icon;
    ``both`` (default) → label + icon.
    """
    mode = str(display)
    if mode == "icon":
        return _ICON_ONLY_LABEL, icon
    if mode == "text":
        return label, None
    return label, icon


def render_action_link(
    label: str,
    *,
    key: str,
    icon: str | None = None,
    on_click: Callable[..., Any] | None = None,
    args: Sequence[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    disabled: bool = False,
    help: str | None = None,
    display: ActionLinkDisplay | str = "both",
) -> bool:
    """Render one Material-icon tertiary link button. Returns click state.

    Non-menu callers omit ``display`` and stay icon+text. Icon-only buttons
    always expose the action name as a hover tooltip (accessible name), even
    when Settings → Interface has turned instructional ⓘ tips off.
    """
    shown_label, shown_icon = action_link_chrome(label, icon, display)
    if str(display) == "icon":
        help_value: str | None = label or None
    else:
        help_value = widget_help(help)
    button_kwargs: dict[str, Any] = {
        "key": action_link_key(key),
        "type": "tertiary",
        "width": "content",
        "on_click": on_click,
        "args": tuple(args) if args is not None else (),
        "kwargs": kwargs or {},
        "disabled": disabled,
        "help": help_value,
    }
    if shown_icon is not None:
        button_kwargs["icon"] = shown_icon
    return bool(st.button(shown_label, **button_kwargs))


def render_download_link(
    label: str,
    *,
    data: Any,
    file_name: str,
    key: str,
    icon: str = ic.DOWNLOAD,
    mime: str | None = None,
    help: str | None = None,
    disabled: bool = False,
) -> bool:
    """Render one Material-icon tertiary download link. Returns click state."""
    return bool(
        st.download_button(
            label,
            data=data,
            file_name=file_name,
            mime=mime,
            key=action_link_key(key),
            type="tertiary",
            width="content",
            icon=icon,
            help=widget_help(help),
            disabled=disabled,
        )
    )
