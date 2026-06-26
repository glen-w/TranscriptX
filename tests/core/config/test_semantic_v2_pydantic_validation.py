"""Pydantic validation tests for semantic_similarity_v2 config subtree."""

from __future__ import annotations

from transcriptx.core.config import get_default_config_dict, validate_config
from transcriptx.core.config.validation import ValidationError

V2_MODE_KEY = "analysis.semantic_similarity_v2.mode"
V2_BATCH_KEY = "analysis.semantic_similarity_v2.batch_size"
V2_THRESHOLD_KEY = "analysis.semantic_similarity_v2.self_similarity_threshold"
V2_ENABLED_KEY = "analysis.semantic_similarity_v2.enabled"


def test_invalid_mode_choice() -> None:
    errors = validate_config(
        {"analysis": {"semantic_similarity_v2": {"mode": "experimental"}}}
    )
    assert V2_MODE_KEY in errors


def test_batch_size_below_min() -> None:
    errors = validate_config(
        {"analysis": {"semantic_similarity_v2": {"batch_size": 0}}}
    )
    assert V2_BATCH_KEY in errors


def test_threshold_above_max() -> None:
    errors = validate_config(
        {"analysis": {"semantic_similarity_v2": {"self_similarity_threshold": 1.5}}}
    )
    assert V2_THRESHOLD_KEY in errors


def test_bool_string_coercion_passes() -> None:
    errors = validate_config(
        {"analysis": {"semantic_similarity_v2": {"enabled": "true"}}}
    )
    assert V2_ENABLED_KEY not in errors


def test_empty_subtree_no_errors() -> None:
    errors = validate_config({})
    v2_errors = {k: v for k, v in errors.items() if k.startswith("analysis.semantic_similarity_v2.")}
    assert v2_errors == {}


def test_valid_override_no_errors() -> None:
    errors = validate_config(
        {"analysis": {"semantic_similarity_v2": {"self_similarity_threshold": 0.81}}}
    )
    assert V2_THRESHOLD_KEY not in errors


def test_partial_override_only() -> None:
    errors = validate_config(
        {"analysis": {"semantic_similarity_v2": {"batch_size": 32}}}
    )
    v2_errors = {k: v for k, v in errors.items() if k.startswith("analysis.semantic_similarity_v2.")}
    assert v2_errors == {}


def test_multiple_invalid_fields() -> None:
    errors = validate_config(
        {
            "analysis": {
                "semantic_similarity_v2": {
                    "mode": "bad",
                    "batch_size": 0,
                }
            }
        }
    )
    assert V2_MODE_KEY in errors
    assert V2_BATCH_KEY in errors


def test_no_double_validation_for_v2_field() -> None:
    errors = validate_config(
        {"analysis": {"semantic_similarity_v2": {"mode": "bad"}}}
    )
    assert len(errors[V2_MODE_KEY]) == 1


def test_validate_default_config_has_no_v2_errors() -> None:
    errors = validate_config(get_default_config_dict())
    v2_errors = {
        k: v for k, v in errors.items() if k.startswith("analysis.semantic_similarity_v2.")
    }
    assert v2_errors == {}


def test_pydantic_validation_error_shape() -> None:
    errors = validate_config({"analysis": {"semantic_similarity_v2": {"mode": "bad"}}})
    assert V2_MODE_KEY in errors
    err = errors[V2_MODE_KEY][0]
    assert isinstance(err, ValidationError)
    assert err.field == V2_MODE_KEY
    assert isinstance(err.message, str) and err.message


def test_validate_config_non_pilot_errors_unchanged() -> None:
    config = get_default_config_dict()
    config["dashboard"] = {"overview_missing_behavior": "unexpected"}
    config["analysis"]["semantic_similarity_v2"] = {"mode": "bad"}
    errors = validate_config(config)
    assert "dashboard.overview_missing_behavior" in errors
    assert V2_MODE_KEY in errors
    dashboard_err = errors["dashboard.overview_missing_behavior"][0]
    assert dashboard_err.field == "dashboard.overview_missing_behavior"
