"""Value coercion utilities for configuration loading."""

from __future__ import annotations

import json
from typing import Any

from .registry import FieldMetadata


def _coerce_bool(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return value


def _coerce_int(value: Any) -> Any:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return value
    return value


def _coerce_float(value: Any) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return value
    return value


def _coerce_list(value: Any) -> Any:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        trimmed = value.strip()
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        if trimmed:
            return [item.strip() for item in trimmed.split(",") if item.strip()]
    return value


def _coerce_dict(value: Any) -> Any:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        trimmed = value.strip()
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return value


def coerce(raw: Any, field_meta: FieldMetadata) -> Any:
    """Coerce raw value to the field's type where possible."""
    if raw is None:
        return None
    target = field_meta.type
    if target is bool:
        return _coerce_bool(raw)
    if target is int:
        return _coerce_int(raw)
    if target is float:
        return _coerce_float(raw)
    if target is list:
        return _coerce_list(raw)
    if target is dict:
        return _coerce_dict(raw)
    return raw
