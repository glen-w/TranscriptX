"""Validation utilities for configuration values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from pydantic import ValidationError as PydanticValidationError

from .models.semantic_similarity_v2 import SemanticSimilarityV2SettingsModel
from .registry import (
    SEMANTIC_SIMILARITY_V2_PREFIX,
    FieldMetadata,
    build_registry,
    flatten,
)

PYDANTIC_VALIDATED_PREFIXES = (f"{SEMANTIC_SIMILARITY_V2_PREFIX}.",)


@dataclass(frozen=True)
class ValidationError:
    field: str
    message: str


def _is_pydantic_validated_key(key: str) -> bool:
    return any(key.startswith(prefix) for prefix in PYDANTIC_VALIDATED_PREFIXES)


def pydantic_errors_to_validation_errors(
    exc: PydanticValidationError,
    dotpath_prefix: str,
) -> Dict[str, List[ValidationError]]:
    """Map Pydantic validation errors to legacy ValidationError dict."""
    errors: Dict[str, List[ValidationError]] = {}
    for err in exc.errors():
        loc = err.get("loc", ())
        field_suffix = ".".join(str(part) for part in loc) if loc else ""
        dotpath = (
            f"{dotpath_prefix}.{field_suffix}" if field_suffix else dotpath_prefix
        )
        message = str(err.get("msg", "Invalid value."))
        errors.setdefault(dotpath, []).append(
            ValidationError(field=dotpath, message=message)
        )
    return errors


def validate_semantic_similarity_v2_subtree(
    subtree: Dict[str, Any],
) -> Dict[str, List[ValidationError]]:
    """Validate semantic_similarity_v2 overrides merged with model defaults."""
    merged = {**SemanticSimilarityV2SettingsModel().model_dump(), **subtree}
    try:
        SemanticSimilarityV2SettingsModel.model_validate(merged)
        return {}
    except PydanticValidationError as exc:
        return pydantic_errors_to_validation_errors(exc, SEMANTIC_SIMILARITY_V2_PREFIX)


def _is_valid_type(value: Any, expected_type: type, allow_none: bool = False) -> bool:
    """Check if a value matches the expected type, with special handling for tuples."""
    # Handle type(None) - this means the field can be None
    if expected_type is type(None):
        return value is None

    # Allow None if explicitly allowed (for optional fields)
    if value is None:
        return allow_none

    if expected_type is bool:
        return isinstance(value, bool)
    if expected_type is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type is tuple:
        # Tuples are often serialized as lists in JSON/config files
        # Accept both tuples and lists for tuple-typed fields
        return isinstance(value, (tuple, list))
    if expected_type is list:
        # Lists can also be tuples in some cases (though less common)
        # But for strict validation, we'll accept both
        return isinstance(value, (list, tuple))
    if expected_type is dict:
        return isinstance(value, dict)
    if expected_type is str:
        return isinstance(value, str)
    return True


def validate(value: Any, field_meta: FieldMetadata) -> List[ValidationError]:
    errors: List[ValidationError] = []

    # Handle None values - allow if default is None or type is None
    if value is None:
        # Allow None if the default is None (optional field) or type is None
        if field_meta.default is None or field_meta.type is type(None):
            return errors
        # Otherwise, None is not allowed
        errors.append(
            ValidationError(
                field_meta.key,
                f"Expected {field_meta.type.__name__}, got None.",
            )
        )
        return errors

    # For optional fields (default is None), allow both the specified type and None
    # But we've already handled None above, so here we just check the type
    # Special case: if type is type(None) but we have a non-None value, and default is None,
    # this is likely an optional field where the type was incorrectly inferred
    # Allow common types (str, int, float, bool, list, dict) for optional fields
    if field_meta.type is type(None) and field_meta.default is None:
        # This is an optional field - allow common types
        if isinstance(value, (str, int, float, bool, list, dict, tuple)):
            # Value is acceptable for an optional field
            pass  # Continue to other validations (min, max, choices, etc.)
        else:
            errors.append(
                ValidationError(
                    field_meta.key,
                    f"Expected NoneType or a valid value type, got {type(value).__name__}.",
                )
            )
            return errors
    elif field_meta.type is type(None):
        # Type is None but default is not None - this shouldn't happen, but be strict
        errors.append(
            ValidationError(
                field_meta.key,
                f"Expected NoneType, got {type(value).__name__}.",
            )
        )
        return errors

    # For optional fields (default is None), allow both the type and None
    # This handles cases like transcription.language which is str | None
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

    v2_prefix = f"{SEMANTIC_SIMILARITY_V2_PREFIX}."
    v2_overrides = {
        key[len(v2_prefix) :]: value
        for key, value in flattened.items()
        if key.startswith(v2_prefix)
    }
    if v2_overrides:
        pydantic_errors = validate_semantic_similarity_v2_subtree(v2_overrides)
        for key, field_errors in pydantic_errors.items():
            if key in flattened:
                errors[key] = field_errors

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
