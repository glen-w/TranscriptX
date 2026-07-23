"""Load JSON configuration file into TranscriptXConfig."""

from __future__ import annotations

import copy
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

# Generic top-level sections applied via flat setattr loops (incremental allowlist).
_GENERIC_FLAT_SECTIONS = frozenset(
    {
        "input",
        "output",
        "dashboard",
        "metadata",
        "logging",
        "audio_preprocessing",
        "group_analysis",
        "llm",
    }
)

_NESTED_ANALYSIS_SUBTREES = frozenset(
    {
        "corrections",
        "highlights",
        "summary",
        "bertopic",
        "pauses",
        "transcript_quality",
        "topic_shift",
        "voice",
        "echoes",
        "momentum",
        "moments",
        "llm_summary",
        "llm_speaker_summary",
        "llm_action_items",
        "llm_custom_qa",
        "group_llm_synthesis",
        "chart_descriptions",
        # Non-adapter nested dataclasses (adapter-owned targets are skipped above).
        "affect_tension",
        "emotion",
        "contextual_emotion",
        "fine_grained_emotion",
        "speaker_exemplars",
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


def _apply_flat_section(section_obj: Any, data: dict[str, Any]) -> None:
    from dataclasses import is_dataclass

    for key, value in data.items():
        if not hasattr(section_obj, key):
            continue
        current = getattr(section_obj, key)
        if isinstance(value, dict) and is_dataclass(current):
            _apply_nested_dict_config(current, value)
            continue
        setattr(section_obj, key, value)


def _apply_overrides_to_candidate(config: Any, config_data: dict[str, Any]) -> None:
    """Mutate ``config`` (expected to be an independent candidate) with file payload."""
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

    for section in _GENERIC_FLAT_SECTIONS:
        if section not in config_data:
            continue
        section_data = config_data[section]
        if not isinstance(section_data, dict):
            continue
        _apply_flat_section(getattr(config, section), section_data)

    if "workflow" in config_data:
        for key, value in config_data["workflow"].items():
            if key == "speaker_gate" and isinstance(value, dict):
                if hasattr(config.workflow, "speaker_gate"):
                    apply_profile_to_config(config.workflow.speaker_gate, value)
            elif hasattr(config.workflow, key):
                apply_profile_to_config(config.workflow, {key: value})

    for adapter in adapters:
        found_activation, activation_name = adapter.get_activation_from_payload(
            config_data
        )
        if found_activation:
            adapter.set_active_profile_name(config, activation_name)
        found_target_payload, target_payload = adapter.get_target_payload(config_data)
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
                    if isinstance(threshold_value, list) and len(threshold_value) == 2:
                        thresholds[threshold_key] = tuple(threshold_value)
        setattr(config.analysis, "quality_filtering_profiles", pending_quality_profiles)

    if "use_emojis" in config_data:
        config.use_emojis = bool(config_data["use_emojis"])

    if "core_mode" in config_data:
        config.core_mode = bool(config_data["core_mode"])


def _commit_dataclass(live_obj: Any, cand_obj: Any) -> None:
    """Copy dataclass fields from candidate into live, preserving nested identities."""
    from dataclasses import fields, is_dataclass

    for f in fields(live_obj):
        live_val = getattr(live_obj, f.name)
        cand_val = getattr(cand_obj, f.name)
        if is_dataclass(live_val) and is_dataclass(cand_val):
            _commit_dataclass(live_val, cand_val)
        elif isinstance(live_val, dict) and isinstance(cand_val, dict):
            live_val.clear()
            live_val.update(cand_val)
        else:
            setattr(live_obj, f.name, cand_val)


def _commit_candidate(live: Any, candidate: Any) -> None:
    """Copy candidate state onto the live config object (preserve object identity)."""
    from dataclasses import is_dataclass

    for name, cand_val in vars(candidate).items():
        if name.startswith("_") or not hasattr(live, name):
            continue
        live_val = getattr(live, name)
        if is_dataclass(live_val) and is_dataclass(cand_val):
            _commit_dataclass(live_val, cand_val)
        else:
            setattr(live, name, cand_val)


def _validate_candidate(candidate: Any) -> None:
    """Validate complete candidate; raise on failure without touching live config."""
    from transcriptx.core.config import validate_config as validate_config_dict
    from transcriptx.core.utils.config import TranscriptXConfig

    if isinstance(candidate, TranscriptXConfig):
        from transcriptx.core.utils.config_validator import validate_config

        result = validate_config(candidate)
        if not result.is_valid:
            error_messages = [str(error) for error in result.errors]
            raise ValueError(
                "Configuration validation failed:\n" + "\n".join(error_messages)
            )

        leaf_errors = validate_config_dict(candidate.to_dict())
        if leaf_errors:
            parts = [
                f"{key}: " + "; ".join(str(err) for err in errs)
                for key, errs in leaf_errors.items()
            ]
            raise ValueError(
                "Configuration leaf validation failed:\n" + "\n".join(parts)
            )


def load_config_file_into(config: Any, config_file: str) -> None:
    """
    Load configuration from JSON file into ``config``.

    Atomic contract: apply overrides to a deep independent candidate, validate the
    complete candidate, and commit onto ``config`` only on success. Failed overrides
    leave the live config (including nested containers and adapter-owned targets)
    unchanged.

    Raises:
        ConfigLoadError: If the file violates the supported config contract
        ValueError: If the file cannot be read or parsed as JSON, or validation fails
    """
    if not os.path.exists(config_file):
        return
    try:
        with open(config_file) as f:
            raw = json.load(f)
        config_data = unwrap_config_payload(raw)
        validate_raw_config_dict(config_data)

        candidate = copy.deepcopy(config)
        _apply_overrides_to_candidate(candidate, config_data)
        _validate_candidate(candidate)
        _commit_candidate(config, candidate)

    except ConfigLoadError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to load configuration from {config_file}: {e}") from e
