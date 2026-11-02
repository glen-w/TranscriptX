"""Shared Pydantic→dataclass hydration helpers (function-local model imports)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def _dataclass_from_nested_dump(cls: type, data: dict[str, Any]) -> object:
    """Build a nested dataclass instance from a model_dump() dict (no __init__)."""
    from dataclasses import is_dataclass
    from typing import get_type_hints

    instance = object.__new__(cls)
    annotations = get_type_hints(cls)
    for key, value in data.items():
        field_type = annotations.get(key)
        if (
            isinstance(value, dict)
            and field_type is not None
            and is_dataclass(field_type)
        ):
            object.__setattr__(
                instance, key, _dataclass_from_nested_dump(field_type, value)
            )
        else:
            object.__setattr__(instance, key, value)
    return instance


def _hydrate_dataclass_from_pydantic(instance: object, model: BaseModel) -> None:
    """Populate dataclass fields from a Pydantic model defaults dump (no revalidation).

    Nested dict values are reconstructed as nested dataclass instances when the
    corresponding field annotation is a dataclass type (needed for summary /
    highlights attribute access and file-override merge).
    """
    from dataclasses import is_dataclass
    from typing import get_type_hints

    annotations = get_type_hints(type(instance))
    for key, value in model.model_dump().items():
        field_type = annotations.get(key)
        if (
            isinstance(value, dict)
            and field_type is not None
            and is_dataclass(field_type)
        ):
            object.__setattr__(
                instance, key, _dataclass_from_nested_dump(field_type, value)
            )
        else:
            object.__setattr__(instance, key, value)


def _hydrate_analysis_slice(instance: object, model: BaseModel) -> None:
    """Hydrate only the fields owned by a partial analysis_* pilot model."""
    from dataclasses import is_dataclass
    from typing import get_type_hints

    annotations = get_type_hints(type(instance))
    for key, value in model.model_dump().items():
        field_type = annotations.get(key)
        if (
            isinstance(value, dict)
            and field_type is not None
            and is_dataclass(field_type)
        ):
            object.__setattr__(
                instance, key, _dataclass_from_nested_dump(field_type, value)
            )
        else:
            object.__setattr__(instance, key, value)


def _hydrate_mapping_store(instance: object, attr_name: str, model: BaseModel) -> None:
    """Set one AnalysisConfig mapping attribute from a fresh model_dump()."""
    object.__setattr__(instance, attr_name, model.model_dump())
