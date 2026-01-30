"""Config form rendering helpers."""

from __future__ import annotations

from typing import Any, Dict, List
import streamlit as st

from transcriptx.core.config.registry import FieldMetadata
from .widgets import render_field_widget


def render_config_form(
    category: str,
    fields: List[FieldMetadata],
    values: Dict[str, Any],
    show_only_changed: bool,
    base_values: Dict[str, Any],
    scope: str,
) -> Dict[str, Any]:
    """Render widgets for a category and return updated dotmap."""
    updated: Dict[str, Any] = {}
    for field_meta in fields:
        key = field_meta.key
        if show_only_changed and base_values.get(key) == values.get(key):
            continue
        widget_key = f"{scope}_{category}_{key}"
        updated_value = render_field_widget(field_meta, values.get(key), widget_key)
        updated[key] = updated_value
    return updated
