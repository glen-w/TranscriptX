"""Convert Pydantic model fields to legacy FieldMetadata registry entries."""

from __future__ import annotations

import copy
import types
from typing import (
    Annotated,
    Any,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .pydantic_bridge_helpers import _nested_base_model
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
    if annotation is None:
        return (str, None)

    origin = get_origin(annotation)
    if origin is Annotated:
        args = get_args(annotation)
        if args:
            return _resolve_field_type(args[0])
        return (str, None)
    if origin is Literal:
        args = get_args(annotation)
        if args and all(isinstance(a, str) for a in args):
            return (str, tuple(args))
        if args:
            return (type(args[0]), tuple(args))
        return (str, None)
    if origin in (Union, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _resolve_field_type(args[0])
    if origin in (list, dict, tuple):
        return (origin, None)
    if annotation in (bool, int, float, str, list, dict, tuple):
        return (annotation, None)
    return (str, None)


def _constraint_bounds(field_info: FieldInfo) -> tuple[float | None, float | None]:
    """Map inclusive Pydantic bounds to registry min/max UI hints.

    ``ge``/``le`` are reflected in FieldMetadata. ``gt``/``lt`` are parsed but
    validation-only (enforced by Pydantic, not exposed as registry bounds).
    """
    metadata = field_info.metadata
    min_val: float | None = None
    max_val: float | None = None
    for item in metadata:
        ge = getattr(item, "ge", None)
        le = getattr(item, "le", None)
        _gt = getattr(item, "gt", None)
        _lt = getattr(item, "lt", None)
        if ge is not None:
            min_val = float(ge)
        elif _gt is not None:
            pass  # exclusive bound: validation-only, not mapped to min
        if le is not None:
            max_val = float(le)
        elif _lt is not None:
            pass  # exclusive bound: validation-only, not mapped to max
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
    """Build FieldMetadata map from a Pydantic model's fields (nested models flattened)."""
    if not category and "." in dotpath_prefix:
        category = dotpath_prefix.split(".", 1)[0]

    hints = get_type_hints(model)
    registry: dict[str, FieldMetadata] = {}
    for name, field_info in model.model_fields.items():
        annotation = hints.get(name, field_info.annotation)
        nested = _nested_base_model(annotation)
        if nested is not None:
            sub_prefix = f"{dotpath_prefix}.{name}"
            registry.update(
                pydantic_model_to_field_metadata(
                    nested,
                    dotpath_prefix=sub_prefix,
                    category=category,
                )
            )
            continue
        key = f"{dotpath_prefix}.{name}"
        field_type, choices = _resolve_field_type(annotation)
        min_val, max_val = _constraint_bounds(field_info)
        extra = _extra_dict(field_info)
        extra_choices = extra.get("choices")
        if extra_choices is not None:
            choices = tuple(extra_choices)
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


def collect_model_leaf_dotpaths(
    model: type[BaseModel],
    *,
    dotpath_prefix: str,
) -> frozenset[str]:
    """Return all leaf field dotpaths for a model tree."""
    hints = get_type_hints(model)
    keys: set[str] = set()
    for name, field_info in model.model_fields.items():
        annotation = hints.get(name, field_info.annotation)
        nested = _nested_base_model(annotation)
        if nested is not None:
            keys.update(
                collect_model_leaf_dotpaths(
                    nested,
                    dotpath_prefix=f"{dotpath_prefix}.{name}",
                )
            )
            continue
        keys.add(f"{dotpath_prefix}.{name}")
    return frozenset(keys)


def serialize_field_metadata(meta: FieldMetadata) -> dict[str, Any]:
    """Serialize FieldMetadata for golden snapshot comparison."""
    type_name = meta.type.__name__ if meta.type is not type(None) else "NoneType"
    default = meta.default
    if isinstance(default, tuple):
        default = list(default)
    return {
        "key": meta.key,
        "path": meta.path,
        "type": type_name,
        "default": default,
        "min": meta.min,
        "max": meta.max,
        "choices": list(meta.choices) if meta.choices is not None else None,
        "description": meta.description,
        "scope": meta.scope,
        "sensitivity": meta.sensitivity,
        "category": meta.category,
        "advanced": meta.advanced,
    }
