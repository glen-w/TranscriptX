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


def _help_text(field_meta: FieldMetadata) -> str | None:
    """Streamlit adjacent ⓘ from FieldMetadata.description when present."""
    text = (field_meta.description or "").strip()
    return text or None


def render_field_widget(field_meta: FieldMetadata, current_value: Any, key: str) -> Any:
    """Render a Streamlit widget for a field and return updated value."""
    if field_meta.sensitivity == "hidden":
        return current_value

    help_text = _help_text(field_meta)

    if field_meta.type is bool:
        return st.checkbox(
            field_meta.key, value=bool(current_value), key=key, help=help_text
        )
    if field_meta.choices is not None:
        options = list(field_meta.choices)
        if field_meta.type in (list, tuple):
            current_list = (
                list(current_value) if isinstance(current_value, (list, tuple)) else []
            )
            return st.multiselect(
                field_meta.key,
                options=options,
                default=[v for v in current_list if v in options],
                key=key,
                help=help_text,
            )
        current = (
            current_value
            if current_value in options
            else (options[0] if options else "")
        )
        return st.selectbox(
            field_meta.key,
            options=options,
            index=options.index(current),
            key=key,
            help=help_text,
        )
    if field_meta.type is int:
        return st.number_input(
            field_meta.key,
            value=int(current_value) if current_value is not None else 0,
            min_value=int(field_meta.min) if field_meta.min is not None else None,
            max_value=int(field_meta.max) if field_meta.max is not None else None,
            step=1,
            key=key,
            help=help_text,
        )
    if field_meta.type is float:
        return st.number_input(
            field_meta.key,
            value=float(current_value) if current_value is not None else 0.0,
            min_value=float(field_meta.min) if field_meta.min is not None else None,
            max_value=float(field_meta.max) if field_meta.max is not None else None,
            key=key,
            help=help_text,
        )
    if field_meta.type in (list, dict):
        raw = st.text_area(
            field_meta.key,
            value=_json_text(current_value) if current_value is not None else "",
            key=key,
            height=120,
            help=help_text,
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
        help=help_text,
    )
