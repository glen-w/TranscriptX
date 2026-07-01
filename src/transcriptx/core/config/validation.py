"""Validation utilities for configuration values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from pydantic import ValidationError as PydanticValidationError

from .pydantic_bridge import (
    PYDANTIC_REGISTRY_PILOTS,
    extract_subtree_overrides,
    is_pydantic_validated_field_key,
)
from .registry import FieldMetadata, build_registry, flatten


@dataclass(frozen=True)
class ValidationError:
    field: str
    message: str


def _is_pydantic_validated_key(key: str) -> bool:
    return is_pydantic_validated_field_key(key)


def pydantic_errors_to_validation_errors(
    exc: PydanticValidationError,
    dotpath_prefix: str,
) -> Dict[str, List[ValidationError]]:
    """Map Pydantic validation errors to legacy ValidationError dict."""
    errors: Dict[str, List[ValidationError]] = {}
    for err in exc.errors():
        loc = err.get("loc", ())
        field_suffix = ".".join(str(part) for part in loc) if loc else ""
        dotpath = f"{dotpath_prefix}.{field_suffix}" if field_suffix else dotpath_prefix
        message = str(err.get("msg", "Invalid value."))
        errors.setdefault(dotpath, []).append(
            ValidationError(field=dotpath, message=message)
        )
    return errors


def _attach_pilot_errors(
    errors: Dict[str, List[ValidationError]],
    pilot_errors: Dict[str, List[ValidationError]],
    flattened: Dict[str, Any],
    *,
    had_overrides: bool,
) -> None:
    """Attach pilot validation errors, fanning parent errors to submitted descendants."""
    for key, field_errors in pilot_errors.items():
        if key in flattened:
            errors[key] = field_errors
            continue
        prefix = f"{key}."
        descendants = sorted(k for k in flattened if k.startswith(prefix))
        if descendants:
            for descendant in descendants:
                errors[descendant] = field_errors
            continue
        if had_overrides:
            errors[key] = field_errors


def validate_pydantic_subtrees(
    flattened: Dict[str, Any],
) -> Dict[str, List[ValidationError]]:
    """Validate all Pydantic pilot subtrees present in a flattened config map."""
    errors: Dict[str, List[ValidationError]] = {}
    for spec in PYDANTIC_REGISTRY_PILOTS:
        overrides = extract_subtree_overrides(flattened, spec)
        if not overrides:
            continue
        merged = {**spec.model().model_dump(), **overrides}
        try:
            spec.model.model_validate(merged)
        except PydanticValidationError as exc:
            pilot_errors = pydantic_errors_to_validation_errors(
                exc, spec.dotpath_prefix
            )
            _attach_pilot_errors(errors, pilot_errors, flattened, had_overrides=True)
    return errors


def _is_valid_type(value: Any, expected_type: type, allow_none: bool = False) -> bool:
    """Check if a value matches the expected type, with special handling for tuples."""
    if expected_type is type(None):
        return value is None

    if value is None:
        return allow_none

    if expected_type is bool:
        return isinstance(value, bool)
    if expected_type is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type is tuple:
        return isinstance(value, (tuple, list))
    if expected_type is list:
        return isinstance(value, (list, tuple))
    if expected_type is dict:
        return isinstance(value, dict)
    if expected_type is str:
        return isinstance(value, str)
    return True


def validate(value: Any, field_meta: FieldMetadata) -> List[ValidationError]:
    errors: List[ValidationError] = []

    if value is None:
        if field_meta.default is None or field_meta.type is type(None):
            return errors
        errors.append(
            ValidationError(
                field_meta.key,
                f"Expected {field_meta.type.__name__}, got None.",
            )
        )
        return errors

    if field_meta.type is type(None) and field_meta.default is None:
        if isinstance(value, (str, int, float, bool, list, dict, tuple)):
            pass
        else:
            errors.append(
                ValidationError(
                    field_meta.key,
                    f"Expected NoneType or a valid value type, got {type(value).__name__}.",
                )
            )
            return errors
    elif field_meta.type is type(None):
        errors.append(
            ValidationError(
                field_meta.key,
                f"Expected NoneType, got {type(value).__name__}.",
            )
        )
        return errors

    allow_none = field_meta.default is None
    if field_meta.type is not type(None) and not _is_valid_type(
        value, field_meta.type, allow_none=allow_none
    ):
        errors.append(
            ValidationError(
                field_meta.key,
                f"Expected {field_meta.type.__name__}, got {type(value).__name__}.",
            )
        )
        return errors

    if field_meta.min is not None and isinstance(value, (int, float)):
        if value < field_meta.min:
            errors.append(
                ValidationError(field_meta.key, f"Value must be >= {field_meta.min}.")
            )
    if field_meta.max is not None and isinstance(value, (int, float)):
        if value > field_meta.max:
            errors.append(
                ValidationError(field_meta.key, f"Value must be <= {field_meta.max}.")
            )
    if field_meta.choices is not None:
        if isinstance(value, (list, tuple)):
            invalid = [item for item in value if item not in field_meta.choices]
            if invalid:
                errors.append(
                    ValidationError(
                        field_meta.key,
                        "Values must be one of: "
                        + ", ".join(map(str, field_meta.choices))
                        + f". Invalid: {', '.join(map(str, invalid))}.",
                    )
                )
        elif value not in field_meta.choices:
            errors.append(
                ValidationError(
                    field_meta.key,
                    f"Value must be one of: {', '.join(map(str, field_meta.choices))}.",
                )
            )
    return errors


def validate_config(config_dict: Dict[str, Any]) -> Dict[str, List[ValidationError]]:
    """Validate a nested config dict and return errors keyed by dotpath."""
    registry = build_registry()
    flattened = flatten(config_dict)
    errors: Dict[str, List[ValidationError]] = {}

    pydantic_errors = validate_pydantic_subtrees(flattened)
    errors.update(pydantic_errors)

    for key, value in flattened.items():
        if _is_pydantic_validated_key(key):
            continue
        meta = registry.get(key)
        if meta is None:
            continue
        field_errors = validate(value, meta)
        if field_errors:
            errors[key] = field_errors
    return errors
