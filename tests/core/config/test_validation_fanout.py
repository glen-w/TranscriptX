"""Tests for Pydantic validation error fan-out to submitted config paths."""

from __future__ import annotations

from transcriptx.core.config import validate_config
from transcriptx.core.config.validation import (
    ValidationError,
    _attach_pilot_errors,
    validate_pydantic_subtrees,
)
from transcriptx.core.config.registry import flatten


def test_attach_pilot_errors_fans_parent_error_to_descendants() -> None:
    errors: dict[str, list[ValidationError]] = {}
    pilot_errors = {
        "workflow.speaker_gate": [
            ValidationError(
                field="workflow.speaker_gate",
                message="percentage threshold too high",
            )
        ]
    }
    flattened = {
        "workflow.speaker_gate.threshold_type": "percentage",
        "workflow.speaker_gate.threshold_value": 101.0,
    }
    _attach_pilot_errors(errors, pilot_errors, flattened, had_overrides=True)
    assert "workflow.speaker_gate.threshold_type" in errors
    assert "workflow.speaker_gate.threshold_value" in errors


def test_attach_pilot_errors_keeps_direct_key_when_present() -> None:
    errors: dict[str, list[ValidationError]] = {}
    field_errors = [ValidationError(field="llm.provider", message="invalid provider")]
    pilot_errors = {"llm.provider": field_errors}
    flattened = {"llm.provider": "openai"}
    _attach_pilot_errors(errors, pilot_errors, flattened, had_overrides=True)
    assert errors["llm.provider"] == field_errors


def test_validate_pydantic_subtrees_surfaces_speaker_gate_percentage_error() -> None:
    payload = {
        "workflow": {
            "speaker_gate": {
                "threshold_type": "percentage",
                "threshold_value": 101.0,
            }
        }
    }
    errors = validate_pydantic_subtrees(flatten(payload))
    assert errors
    assert (
        "workflow.speaker_gate.threshold_value" in errors
        or "workflow.speaker_gate" in errors
    )


def test_validate_config_nested_workflow_gate_error_not_silently_dropped() -> None:
    errors = validate_config(
        {
            "workflow": {
                "speaker_gate": {
                    "threshold_type": "percentage",
                    "threshold_value": 150.0,
                }
            }
        }
    )
    assert errors
    assert any(key.startswith("workflow.speaker_gate") for key in errors)
