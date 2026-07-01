"""Pydantic schema for workflow settings."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ThresholdType = Literal["absolute", "percentage"]
SpeakerGateMode = Literal["ignore", "warn", "enforce"]

_SPEAKER_GATE_DEFAULTS: dict[str, Any] = {
    "threshold_value": 0.0,
    "threshold_type": "absolute",
    "mode": "warn",
    "exemplar_count": 2,
}


def speaker_gate_settings_payload_from_applied(gate: Any) -> dict[str, Any]:
    """Merge applied speaker_gate config (dict or dataclass) with model defaults."""
    defaults = dict(_SPEAKER_GATE_DEFAULTS)
    if isinstance(gate, dict):
        return {**defaults, **gate}
    return {
        **defaults,
        **{name: getattr(gate, name) for name in _SPEAKER_GATE_DEFAULTS},
    }


def validate_speaker_gate_applied(gate: Any) -> None:
    """Validate applied speaker gate settings (shared with validate_config)."""
    payload = speaker_gate_settings_payload_from_applied(gate)
    threshold_type = str(payload.get("threshold_type", "absolute")).strip().lower()
    threshold_value = float(payload.get("threshold_value", 0.0))
    if threshold_type == "percentage" and threshold_value > 100.0:
        raise ValueError(
            "workflow.speaker_gate.threshold_value must be <= 100 when "
            "threshold_type is 'percentage'."
        )


class SpeakerGateSettingsModel(BaseModel):
    """Speaker identification gate settings."""

    threshold_type: ThresholdType = Field(default="absolute")
    threshold_value: float = Field(default=0.0, ge=0.0)
    mode: SpeakerGateMode = Field(default="warn")
    exemplar_count: int = Field(default=2, ge=0)

    @field_validator("threshold_value")
    @classmethod
    def _cap_percentage_threshold(cls, value: float, info: Any) -> float:
        threshold_type = info.data.get("threshold_type", "absolute")
        if threshold_type == "percentage" and value > 100.0:
            raise ValueError(
                "workflow.speaker_gate.threshold_value must be <= 100 when "
                "threshold_type is 'percentage'."
            )
        return value


class WorkflowSettingsModel(BaseModel):
    """Canonical field definitions for workflow and batch processing."""

    timeout_quick_seconds: int = Field(default=3600, ge=1)
    timeout_full_seconds: int = Field(default=7200, ge=1)
    update_interval: float = Field(default=10.0, ge=0.1)
    max_size_mb: int = Field(default=30, ge=1)
    subprocess_timeout: int = Field(default=5, ge=1)
    mp3_bitrate: str = Field(default="192k")
    conversion_time_factor: float = Field(default=0.5, ge=0.0)
    speaker_gate: SpeakerGateSettingsModel = Field(
        default_factory=SpeakerGateSettingsModel
    )
    cli_pruning_enabled: bool = Field(default=False)
    default_config_save_path: str = Field(default="")
