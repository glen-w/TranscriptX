"""Convert Pydantic model fields to legacy FieldMetadata registry entries."""

from __future__ import annotations

import copy
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .registry import FieldMetadata

_TYPE_MAP: dict[str, type] = {
    "bool": bool,
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "NoneType": type(None),
}


def _resolve_field_type(annotation: Any) -> tuple[type, tuple[Any, ...] | None]:
    """Return (python_type, literal_choices_or_none)."""
    origin = get_origin(annotation)
    if origin is Literal:
        args = get_args(annotation)
        if args and all(isinstance(a, str) for a in args):
            return (str, tuple(args))
        if args:
            return (type(args[0]), tuple(args))
        return (str, None)
    if origin is Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _resolve_field_type(args[0])
    if annotation in (bool, int, float, str, list, dict, tuple):
        return (annotation, None)
    return (str, None)


def _constraint_bounds(field_info: FieldInfo) -> tuple[float | None, float | None]:
    metadata = field_info.metadata
    min_val: float | None = None
    max_val: float | None = None
    for item in metadata:
        ge = getattr(item, "ge", None)
        le = getattr(item, "le", None)
        if ge is not None:
            min_val = float(ge)
        if le is not None:
            max_val = float(le)
    return min_val, max_val


def _extra_dict(field_info: FieldInfo) -> dict[str, Any]:
    extra = field_info.json_schema_extra
    if isinstance(extra, dict):
        return extra
    if callable(extra):
        # Pydantic may store a callable; invoke with a minimal schema dict.
        schema: dict[str, Any] = {}
        extra(schema)
        return schema
    return {}


def pydantic_model_to_field_metadata(
    model: type[BaseModel],
    *,
    dotpath_prefix: str,
    category: str = "",
) -> dict[str, FieldMetadata]:
    """Build FieldMetadata map from a Pydantic model's fields."""
    if not category and "." in dotpath_prefix:
        category = dotpath_prefix.split(".", 1)[0]

    registry: dict[str, FieldMetadata] = {}
    for name, field_info in model.model_fields.items():
        key = f"{dotpath_prefix}.{name}"
        field_type, choices = _resolve_field_type(field_info.annotation)
        min_val, max_val = _constraint_bounds(field_info)
        extra = _extra_dict(field_info)
        default = field_info.get_default(call_default_factory=True)
        registry[key] = FieldMetadata(
            key=key,
            path=key,
            type=field_type,
            default=copy.deepcopy(default),
            min=min_val,
            max=max_val,
            choices=list(choices) if choices is not None else None,
            description=field_info.description or "",
            scope=str(extra.get("scope", "project")),
            sensitivity=str(extra.get("sensitivity", "normal")),
            category=str(extra.get("category", category)),
            advanced=bool(extra.get("advanced", False)),
        )
    return registry


def serialize_field_metadata(meta: FieldMetadata) -> dict[str, Any]:
    """Serialize FieldMetadata for golden snapshot comparison."""
    type_name = meta.type.__name__ if meta.type is not type(None) else "NoneType"
    return {
        "key": meta.key,
        "path": meta.path,
        "type": type_name,
        "default": meta.default,
        "min": meta.min,
        "max": meta.max,
        "choices": list(meta.choices) if meta.choices is not None else None,
        "description": meta.description,
        "scope": meta.scope,
        "sensitivity": meta.sensitivity,
        "category": meta.category,
        "advanced": meta.advanced,
    }
