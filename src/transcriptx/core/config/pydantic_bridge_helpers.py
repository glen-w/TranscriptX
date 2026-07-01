"""Shared behavioral helpers for Pydantic config bridge (dotpath routing, override extraction)."""

from __future__ import annotations

import types
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel


def _nested_base_model(annotation: Any) -> type[BaseModel] | None:
    if annotation is None or isinstance(annotation, str):
        return None
    origin = get_origin(annotation)
    if origin is Annotated:
        args = get_args(annotation)
        if args:
            return _nested_base_model(args[0])
        return None
    if origin in (Union, types.UnionType):
        for arg in get_args(annotation):
            if arg is type(None):
                continue
            nested = _nested_base_model(arg)
            if nested is not None:
                return nested
        return None
    if origin is not None:
        return None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def dotpath_belongs_to_model(
    key: str,
    *,
    dotpath_prefix: str,
    model: type[BaseModel],
) -> bool:
    """Return True when ``key`` is a leaf field dotpath on ``model`` under ``dotpath_prefix``."""
    prefix = f"{dotpath_prefix}."
    if not key.startswith(prefix):
        return False
    remainder = key[len(prefix) :]
    if not remainder:
        return False
    parts = remainder.split(".")
    current = model
    for index, part in enumerate(parts):
        if part not in current.model_fields:
            return False
        field_info = current.model_fields[part]
        current_hints = get_type_hints(current)
        annotation = current_hints.get(part, field_info.annotation)
        nested = _nested_base_model(annotation)
        if nested is not None:
            if index == len(parts) - 1:
                return False
            current = nested
            continue
        return index == len(parts) - 1
    return False


def extract_subtree_overrides(
    flattened: dict[str, Any],
    *,
    dotpath_prefix: str,
    model: type[BaseModel],
) -> dict[str, Any]:
    """Rebuild nested override dict from flattened dotpath keys for one pilot subtree."""
    prefix = f"{dotpath_prefix}."
    overrides: dict[str, Any] = {}
    for key, value in flattened.items():
        if not key.startswith(prefix):
            continue
        if not dotpath_belongs_to_model(
            key,
            dotpath_prefix=dotpath_prefix,
            model=model,
        ):
            continue
        suffix = key[len(prefix) :]
        cursor: dict[str, Any] = overrides
        parts = suffix.split(".")
        for part in parts[:-1]:
            nested = cursor.get(part)
            if not isinstance(nested, dict):
                nested = {}
                cursor[part] = nested
            cursor = nested
        cursor[parts[-1]] = value
    return overrides
