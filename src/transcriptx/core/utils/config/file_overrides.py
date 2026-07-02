"""Load JSON configuration file into TranscriptXConfig."""

from __future__ import annotations

import json
import os
from typing import Any

from transcriptx.core.config import iter_all_profile_target_adapters
from transcriptx.core.utils.config.config_errors import ConfigLoadError
from transcriptx.core.utils.config.config_raw_validation import (
    unwrap_config_payload,
    validate_raw_config_dict,
)
from transcriptx.core.utils.config.profile_loading import apply_profile_to_config

_NESTED_ANALYSIS_SUBTREES = frozenset(
    {
        "corrections",
        "highlights",
        "summary",
        "bertopic",
        "pauses",
        "voice",
        "echoes",
        "momentum",
        "moments",
        "llm_summary",
    }
)


def _apply_nested_dict_config(config_obj: Any, data: dict[str, Any]) -> None:
    """Recursively apply nested dict payloads onto dataclass config objects."""
    from dataclasses import is_dataclass

    for key, value in data.items():
        if not hasattr(config_obj, key):
            continue
        current = getattr(config_obj, key)
        if isinstance(value, dict):
            if is_dataclass(type(current)):
                _apply_nested_dict_config(current, value)
                continue
            if isinstance(current, dict):
                setattr(config_obj, key, {**current, **value})
                continue
        if isinstance(value, list) and len(value) == 2:
            try:
                if all(isinstance(x, (int, float)) for x in value):
                    value = tuple(value)
            except (ValueError, TypeError):
                pass
        setattr(config_obj, key, value)
    if hasattr(config_obj, "validate"):
        config_obj.validate()


def load_config_file_into(config: Any, config_file: str) -> None:
    """
    Load configuration from JSON file into ``config``.

    Raises:
        ConfigLoadError: If the file violates the supported config contract
        ValueError: If the file cannot be read or parsed as JSON
    """
    if not os.path.exists(config_file):
        return
    try:
        with open(config_file) as f:
            raw = json.load(f)
        config_data = unwrap_config_payload(raw)
        validate_raw_config_dict(config_data)

        adapters = iter_all_profile_target_adapters()
        analysis_target_config_keys = {
            adapter.config_path[1]
            for adapter in adapters
            if len(adapter.config_path) == 2 and adapter.config_path[0] == "analysis"
        }
        pending_quality_profiles: dict[str, Any] | None = None

        if "analysis" in config_data:
            for key, value in config_data["analysis"].items():
                if key == "quality_filtering_profiles" and isinstance(value, dict):
                    pending_quality_profiles = value
                elif key in analysis_target_config_keys and isinstance(value, dict):
                    # Adapter-owned target config application happens below.
                    continue
                elif key in _NESTED_ANALYSIS_SUBTREES and isinstance(value, dict):
                    _apply_nested_dict_config(getattr(config.analysis, key), value)
                elif hasattr(config.analysis, key):
                    setattr(config.analysis, key, value)

        if "input" in config_data:
            for key, value in config_data["input"].items():
                if hasattr(config.input, key):
                    setattr(config.input, key, value)

        if "output" in config_data:
            for key, value in config_data["output"].items():
                if hasattr(config.output, key):
                    setattr(config.output, key, value)

        if "dashboard" in config_data:
            dashboard_data = config_data["dashboard"]
            if isinstance(dashboard_data, dict):
                for key, value in dashboard_data.items():
                    if hasattr(config.dashboard, key):
                        setattr(config.dashboard, key, value)

        if "metadata" in config_data:
            metadata_data = config_data["metadata"]
            if isinstance(metadata_data, dict):
                for key, value in metadata_data.items():
                    if hasattr(config.metadata, key):
                        setattr(config.metadata, key, value)

        if "logging" in config_data:
            for key, value in config_data["logging"].items():
                if hasattr(config.logging, key):
                    setattr(config.logging, key, value)

        if "audio_preprocessing" in config_data:
            for key, value in config_data["audio_preprocessing"].items():
                if hasattr(config.audio_preprocessing, key):
                    setattr(config.audio_preprocessing, key, value)

        if "workflow" in config_data:
            for key, value in config_data["workflow"].items():
                if key == "speaker_gate" and isinstance(value, dict):
                    if hasattr(config.workflow, "speaker_gate"):
                        apply_profile_to_config(config.workflow.speaker_gate, value)
                elif hasattr(config.workflow, key):
                    apply_profile_to_config(config.workflow, {key: value})

        if "group_analysis" in config_data:
            for key, value in config_data["group_analysis"].items():
                if hasattr(config.group_analysis, key):
                    setattr(config.group_analysis, key, value)

        if "llm" in config_data:
            llm_data = config_data["llm"]
            if isinstance(llm_data, dict):
                for key, value in llm_data.items():
                    if hasattr(config.llm, key):
                        setattr(config.llm, key, value)

        for adapter in adapters:
            found_activation, activation_name = adapter.get_activation_from_payload(
                config_data
            )
            if found_activation:
                adapter.set_active_profile_name(config, activation_name)
            found_target_payload, target_payload = adapter.get_target_payload(
                config_data
            )
            if found_target_payload and adapter.target_id != "workflow":
                config_obj = adapter.get_target_config_obj(config)
                if config_obj is not None:
                    apply_profile_to_config(config_obj, target_payload)

        # Deterministic apply order:
        # 1) base file overrides
        # 2) adapter-target payload application
        # 3) special-case bucket normalization/repair where required
        if pending_quality_profiles is not None:
            for profile_data in pending_quality_profiles.values():
                if isinstance(profile_data, dict) and "thresholds" in profile_data:
                    thresholds = profile_data["thresholds"]
                    for threshold_key, threshold_value in thresholds.items():
                        if (
                            isinstance(threshold_value, list)
                            and len(threshold_value) == 2
                        ):
                            thresholds[threshold_key] = tuple(threshold_value)
            setattr(
                config.analysis, "quality_filtering_profiles", pending_quality_profiles
            )

        if "use_emojis" in config_data:
            config.use_emojis = bool(config_data["use_emojis"])

        if "core_mode" in config_data:
            config.core_mode = bool(config_data["core_mode"])

    except ConfigLoadError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to load configuration from {config_file}: {e}") from e
