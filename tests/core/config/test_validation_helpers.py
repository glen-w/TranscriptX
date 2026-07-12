"""Unit tests for config.validation field helpers and type checks."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError
from pydantic import BaseModel, Field

from transcriptx.core.config.registry import FieldMetadata
from transcriptx.core.config.validation import (
    ValidationError,
    _attach_pilot_errors,
    _is_valid_type,
    pydantic_errors_to_validation_errors,
    validate,
)


def _meta(
    *,
    key: str = "analysis.sample",
    typ: type = int,
    default: object = 0,
    min_v: float | None = None,
    max_v: float | None = None,
    choices: list | None = None,
) -> FieldMetadata:
    return FieldMetadata(
        key=key,
        path=key,
        type=typ,
        default=default,
        min=min_v,
        max=max_v,
        choices=choices,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "value,expected_type,allow_none,ok",
    [
        (None, type(None), False, True),
        (1, type(None), False, False),
        (None, int, True, True),
        (None, int, False, False),
        (True, bool, False, True),
        (1, bool, False, False),
        (3, int, False, True),
        (True, int, False, False),
        (1.5, float, False, True),
        (2, float, False, True),
        (True, float, False, False),
        ((1, 2), tuple, False, True),
        ([1, 2], tuple, False, True),
        ([1], list, False, True),
        ((1,), list, False, True),
        ({"a": 1}, dict, False, True),
        ("x", str, False, True),
        (object(), object, False, True),  # unknown expected type → True
    ],
)
def test_is_valid_type_matrix(
    value: object, expected_type: type, allow_none: bool, ok: bool
) -> None:
    assert _is_valid_type(value, expected_type, allow_none=allow_none) is ok


@pytest.mark.unit
def test_validate_none_allowed_when_default_none() -> None:
    assert validate(None, _meta(typ=int, default=None)) == []


@pytest.mark.unit
def test_validate_none_rejected_when_default_set() -> None:
    errors = validate(None, _meta(typ=int, default=5))
    assert len(errors) == 1
    assert "got None" in errors[0].message


@pytest.mark.unit
def test_validate_none_type_field_accepts_scalars() -> None:
    assert validate("ok", _meta(typ=type(None), default=None)) == []


@pytest.mark.unit
def test_validate_none_type_field_rejects_non_scalars() -> None:
    errors = validate(object(), _meta(typ=type(None), default=None))
    assert errors and "NoneType" in errors[0].message


@pytest.mark.unit
def test_validate_none_type_with_non_none_default_rejects_value() -> None:
    errors = validate("x", _meta(typ=type(None), default="sentinel"))
    assert errors and "Expected NoneType" in errors[0].message


@pytest.mark.unit
def test_validate_type_mismatch() -> None:
    errors = validate("bad", _meta(typ=int, default=0))
    assert errors and "Expected int" in errors[0].message


@pytest.mark.unit
def test_validate_min_max_and_choices() -> None:
    assert validate(5, _meta(typ=int, min_v=1, max_v=10)) == []
    assert "must be >=" in validate(0, _meta(typ=int, min_v=1))[0].message
    assert "must be <=" in validate(11, _meta(typ=int, max_v=10))[0].message

    choice_meta = _meta(typ=str, default="a", choices=["a", "b"])
    assert validate("a", choice_meta) == []
    assert "must be one of" in validate("c", choice_meta)[0].message

    list_meta = _meta(typ=list, default=[], choices=["a", "b"])
    assert validate(["a", "b"], list_meta) == []
    err = validate(["a", "z"], list_meta)[0].message
    assert "Invalid: z" in err


@pytest.mark.unit
def test_pydantic_errors_to_validation_errors_maps_loc() -> None:
    class M(BaseModel):
        n: int = Field(ge=1)

    try:
        M.model_validate({"n": 0})
    except PydanticValidationError as exc:
        mapped = pydantic_errors_to_validation_errors(exc, "analysis.pilot")
    assert "analysis.pilot.n" in mapped
    assert isinstance(mapped["analysis.pilot.n"][0], ValidationError)


@pytest.mark.unit
def test_attach_pilot_errors_fans_out_and_keeps_parent() -> None:
    errors: dict = {}
    pilot = {
        "analysis.pilot": [ValidationError("analysis.pilot", "bad")],
        "analysis.other": [ValidationError("analysis.other", "also")],
    }
    flattened = {
        "analysis.pilot.child_a": 1,
        "analysis.pilot.child_b": 2,
    }
    _attach_pilot_errors(errors, pilot, flattened, had_overrides=True)
    assert "analysis.pilot.child_a" in errors
    assert "analysis.pilot.child_b" in errors
    assert "analysis.other" in errors  # no descendants, had_overrides → keep key

    errors2: dict = {}
    _attach_pilot_errors(
        errors2,
        {"analysis.missing": [ValidationError("analysis.missing", "x")]},
        {},
        had_overrides=False,
    )
    assert errors2 == {}
