"""Pydantic schema for llm.* settings."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMModelSelectionSettingsModel(BaseModel):
    """Named / run-scoped model pack applied via ``llm_models`` profiles."""

    model_config = ConfigDict(protected_namespaces=())

    mode: Literal["shared", "per_module"] = Field(
        default="shared",
        description="Use one shared model for all LLM consumers, or pick per consumer.",
    )
    shared_model: str | None = Field(
        default=None,
        description="Model tag used in shared mode (and as per-module fallback).",
    )
    module_models: dict[str, str] = Field(
        default_factory=dict,
        description="Optional per-consumer Ollama model tags when mode is per_module.",
    )


class LLMSettingsModel(BaseModel):
    """Canonical field definitions for LLM provider configuration."""

    model_config = ConfigDict(protected_namespaces=())

    enabled: bool = Field(
        default=False,
        description="Enable LLM-backed analysis modules when provider is available.",
    )
    provider: Literal["null", "ollama"] = Field(
        default="null",
        description="LLM provider id (`null` disables remote calls; `ollama` uses a local server).",
    )
    model: str | None = Field(
        default=None,
        description="Provider model name (e.g. Ollama tag).",
    )
    base_url: str | None = Field(
        default=None,
        description="Provider base URL (e.g. http://localhost:11434/).",
    )
    request_timeout: float = Field(
        default=1350.0,
        gt=0,
        description="Per-request timeout in seconds for LLM calls.",
    )
    availability_timeout: float = Field(
        default=7.5,
        gt=0,
        description="Timeout in seconds when probing provider availability.",
    )
    seed: int = Field(
        default=42,
        description="Default seed for reproducible generation where supported.",
    )
    max_input_chars: int = Field(
        default=48_000,
        description="Maximum characters of transcript text sent to the LLM after prompt wrapping.",
    )
    max_output_tokens: int | None = Field(
        default=2048,
        description="Optional cap on generated tokens.",
    )
    default_temperature: float = Field(
        default=0.3,
        ge=0,
        description="Default sampling temperature for modules that do not override per call.",
    )
    active_model_profile: str = Field(
        default="default",
        description="Active llm_models profile name (virtual default when unset).",
    )
    model_selection: LLMModelSelectionSettingsModel = Field(
        default_factory=LLMModelSelectionSettingsModel,
        description="Resolved model pack from the active llm_models profile.",
    )

    @field_validator("max_input_chars")
    @classmethod
    def _max_input_chars_floor(cls, value: int) -> int:
        from transcriptx.core.llm.prompting import prompt_envelope_min_chars

        min_chars = prompt_envelope_min_chars()
        if value < min_chars:
            raise ValueError(
                f"llm.max_input_chars ({value}) is below the minimum required "
                f"for the LLM prompt envelope ({min_chars} characters)."
            )
        return value

    @field_validator("max_output_tokens")
    @classmethod
    def _max_output_tokens_ge_one_when_set(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("max_output_tokens must be >= 1 when set.")
        return value


def llm_settings_payload_from_applied(llm: Any) -> dict[str, Any]:
    """Merge applied llm config (dict or dataclass) with model defaults."""
    from dataclasses import asdict, is_dataclass

    defaults = LLMSettingsModel().model_dump()
    if isinstance(llm, dict):
        return {**defaults, **llm}
    payload: dict[str, Any] = {}
    for name in LLMSettingsModel.model_fields:
        value = getattr(llm, name, defaults.get(name))
        if is_dataclass(value) and not isinstance(value, type):
            value = asdict(value)
        payload[name] = value
    return {**defaults, **payload}


def validate_llm_settings_applied(llm: Any) -> None:
    """Validate applied LLM settings; raises ConfigLoadError on failure."""
    from pydantic import ValidationError as PydanticValidationError

    from transcriptx.core.utils.config.config_errors import ConfigLoadError

    payload = llm_settings_payload_from_applied(llm)
    try:
        LLMSettingsModel.model_validate(payload)
    except PydanticValidationError as exc:
        message = _first_pydantic_message(exc)
        raise ConfigLoadError(message, code="invalid_value") from exc


def _first_pydantic_message(exc: Any) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid LLM configuration."
    return str(errors[0].get("msg", "Invalid LLM configuration."))
