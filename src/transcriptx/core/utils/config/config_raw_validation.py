"""Validate raw JSON config payloads before applying them to TranscriptXConfig."""

from __future__ import annotations

from typing import Any

from transcriptx.core.utils.config.config_errors import ConfigLoadError

# Top-level keys accepted in a flat JSON config (after optional wrapper unwrap).
_ALLOWED_TOP_LEVEL_KEYS = frozenset(
    {
        "analysis",
        "input",
        "output",
        "dashboard",
        "logging",
        "audio_preprocessing",
        "workflow",
        "group_analysis",
        "llm",
        "active_workflow_profile",
        "use_emojis",
        "core_mode",
    }
)

_LLM_ALLOWED_KEYS = frozenset(
    {
        "enabled",
        "provider",
        "model",
        "base_url",
        "api_key",
        "request_timeout",
        "availability_timeout",
        "seed",
        "max_input_chars",
        "max_output_tokens",
        "default_temperature",
    }
)

_LEGACY_AUDIO_BOOL_KEYS = frozenset(
    {
        "normalize_enabled",
        "denoise_enabled",
        "highpass_enabled",
        "lowpass_enabled",
        "bandpass_enabled",
    }
)

# Fields that must use mode strings (auto/suggest/off) or global mode — not bools.
_AUDIO_MODE_STRING_FIELDS = frozenset(
    {
        "preprocessing_mode",
        "convert_to_mono",
        "downsample",
        "normalize_mode",
        "denoise_mode",
        "highpass_mode",
        "lowpass_mode",
        "bandpass_mode",
    }
)


def unwrap_config_payload(raw: Any) -> dict[str, Any]:
    """Return the inner config dict (unwrap project wrapper if present)."""
    if not isinstance(raw, dict):
        raise ConfigLoadError(
            "Configuration root must be a JSON object.",
            code="invalid_value",
        )
    data = raw
    if (
        "config" in data
        and "schema_version" in data
        and isinstance(data.get("config"), dict)
    ):
        inner = data["config"]
        if not isinstance(inner, dict):
            raise ConfigLoadError(
                '"config" must be a JSON object when using the wrapped format.',
                code="invalid_value",
            )
        return inner
    return data


def validate_raw_config_dict(config_data: dict[str, Any]) -> None:
    """
    Validate raw JSON before merging into TranscriptXConfig.

    Raises ConfigLoadError with a migration-directional message when the file
    uses removed shapes (no silent upgrade).
    """
    for key in config_data:
        if key not in _ALLOWED_TOP_LEVEL_KEYS:
            if key == "transcription":
                raise ConfigLoadError(
                    'Unsupported configuration section "transcription". '
                    "TranscriptX is analysis-only; remove this section from your config file.",
                    code="unknown_section",
                )
            raise ConfigLoadError(
                f'Unknown configuration section "{key}". '
                "Remove unsupported top-level keys from the file.",
                code="unknown_section",
            )

    dash = config_data.get("dashboard")
    if isinstance(dash, dict):
        if "overview_chart_types" in dash:
            raise ConfigLoadError(
                'Unsupported dashboard key "overview_chart_types". '
                'Use "overview_charts" (list of chart ids) with "schema_version": 2.',
                code="unsupported_legacy_shape",
            )

    llm = config_data.get("llm")
    if isinstance(llm, dict):
        for k in llm:
            if k not in _LLM_ALLOWED_KEYS:
                raise ConfigLoadError(
                    f'Unknown llm configuration key "{k}". '
                    f"Allowed keys: {sorted(_LLM_ALLOWED_KEYS)}.",
                    code="unknown_section",
                )

    audio = config_data.get("audio_preprocessing")
    if isinstance(audio, dict):
        for k, v in audio.items():
            if k in _LEGACY_AUDIO_BOOL_KEYS:
                raise ConfigLoadError(
                    f'Unsupported audio_preprocessing key "{k}". '
                    "Use the corresponding *_mode field "
                    "(e.g. normalize_mode, denoise_mode) with values "
                    '"auto", "suggest", or "off".',
                    code="unsupported_legacy_shape",
                )
            if k in _AUDIO_MODE_STRING_FIELDS and isinstance(v, bool):
                raise ConfigLoadError(
                    f"Boolean value for audio_preprocessing.{k} is not accepted. "
                    'Use mode strings: "auto", "suggest", or "off".',
                    code="unsupported_legacy_shape",
                )
