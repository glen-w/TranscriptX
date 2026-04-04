"""Load JSON configuration file into TranscriptXConfig."""

from __future__ import annotations

import json
import os
from typing import Any

from transcriptx.core.utils.config.config_errors import ConfigLoadError
from transcriptx.core.utils.config.config_raw_validation import (
    unwrap_config_payload,
    validate_raw_config_dict,
)
from transcriptx.core.utils.config.profile_loading import apply_profile_to_config


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

        if "analysis" in config_data:
            for key, value in config_data["analysis"].items():
                if key in (
                    "topic_modeling",
                    "acts",
                    "tag_extraction",
                    "qa_analysis",
                    "temporal_dynamics",
                    "vectorization",
                    "voice",
                    "speaker_exemplars",
                    "affect_tension",
                ):
                    config_obj = getattr(config.analysis, key)
                    if isinstance(value, dict):
                        apply_profile_to_config(config_obj, value)
                elif key.startswith("active_") and key.endswith("_profile"):
                    setattr(config.analysis, key, value)
                elif key == "quality_filtering_profiles" and isinstance(value, dict):
                    for profile_name, profile_data in value.items():
                        if (
                            isinstance(profile_data, dict)
                            and "thresholds" in profile_data
                        ):
                            thresholds = profile_data["thresholds"]
                            for threshold_key, threshold_value in thresholds.items():
                                if (
                                    isinstance(threshold_value, list)
                                    and len(threshold_value) == 2
                                ):
                                    thresholds[threshold_key] = tuple(threshold_value)
                    setattr(config.analysis, key, value)
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

        if "active_workflow_profile" in config_data:
            config.active_workflow_profile = config_data["active_workflow_profile"]

        if "use_emojis" in config_data:
            config.use_emojis = bool(config_data["use_emojis"])

        if "core_mode" in config_data:
            config.core_mode = bool(config_data["core_mode"])

    except ConfigLoadError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to load configuration from {config_file}: {e}") from e
