"""Compact tertiary icon-links for navigation and download actions."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import streamlit as st
from transcriptx.web import icons as ic
from transcriptx.web.components.info_tooltip import widget_help

# Streamlit exposes widget keys as ``st-key-<key>`` CSS classes; this prefix
# scopes shared action-link styling in shell.py.
ACTION_LINK_KEY_PREFIX = "tx_al_"


def action_link_key(key: str) -> str:
    if key.startswith(ACTION_LINK_KEY_PREFIX):
        return key
    return f"{ACTION_LINK_KEY_PREFIX}{key}"


def render_action_link(
    label: str,
    *,
    key: str,
    icon: str,
    on_click: Callable[..., Any] | None = None,
    args: Sequence[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    disabled: bool = False,
    help: str | None = None,
) -> bool:
    """Render one Material-icon tertiary link button. Returns click state."""
    return bool(
        st.button(
            label,
            key=action_link_key(key),
            type="tertiary",
            width="content",
            icon=icon,
            on_click=on_click,
            args=tuple(args) if args is not None else (),
            kwargs=kwargs or {},
            disabled=disabled,
            help=widget_help(help),
        )
    )


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
