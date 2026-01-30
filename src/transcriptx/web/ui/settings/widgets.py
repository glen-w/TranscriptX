"""Widget mapping for configuration fields."""

from __future__ import annotations

from typing import Any
import json
import streamlit as st

from transcriptx.core.config.registry import FieldMetadata


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, indent=2)
    except TypeError:
        return str(value)


def render_field_widget(field_meta: FieldMetadata, current_value: Any, key: str) -> Any:
    """Render a Streamlit widget for a field and return updated value."""
    if field_meta.sensitivity == "hidden":
        return current_value

    if field_meta.type is bool:
        return st.checkbox(field_meta.key, value=bool(current_value), key=key)
    if field_meta.type is int:
        return st.number_input(
            field_meta.key,
            value=int(current_value) if current_value is not None else 0,
            step=1,
            key=key,
        )
    if field_meta.type is float:
        return st.number_input(
            field_meta.key,
            value=float(current_value) if current_value is not None else 0.0,
            key=key,
        )
    if field_meta.type in (list, dict):
        raw = st.text_area(
            field_meta.key,
            value=_json_text(current_value) if current_value is not None else "",
            key=key,
            height=120,
        )
        try:
            parsed = json.loads(raw) if raw else current_value
        except json.JSONDecodeError:
            parsed = current_value
        return parsed
    return st.text_input(
        field_meta.key,
        value=str(current_value) if current_value is not None else "",
        key=key,
    )
