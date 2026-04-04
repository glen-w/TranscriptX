"""Apply profile data and load module profiles onto TranscriptXConfig."""

from __future__ import annotations

import os
from typing import Any


def apply_profile_to_config(config_obj: Any, profile_data: dict[str, Any]) -> None:
    """
    Apply profile data to a config object.

    Args:
        config_obj: The config dataclass instance to update
        profile_data: Dictionary with profile settings
    """
    for key, value in profile_data.items():
        if hasattr(config_obj, key):
            if isinstance(value, list) and len(value) == 2:
                try:
                    if all(isinstance(x, (int, float)) for x in value):
                        value = tuple(value)
                except (ValueError, TypeError):
                    pass
            setattr(config_obj, key, value)
    if hasattr(config_obj, "validate"):
        config_obj.validate()


def load_module_profiles(config: Any) -> None:
    """
    Load active profiles for each module onto ``config``.

    Profile settings override defaults and file settings but not environment variables.
    If a profile doesn't exist, the default values from the dataclass are used.
    """
    from transcriptx.core.utils.profile_manager import get_profile_manager

    profile_manager = get_profile_manager()

    topic_profile = profile_manager.load_profile(
        "topic_modeling", config.analysis.active_topic_modeling_profile
    )
    if topic_profile and "config" in topic_profile:
        apply_profile_to_config(config.analysis.topic_modeling, topic_profile["config"])

    acts_profile = profile_manager.load_profile(
        "acts", config.analysis.active_acts_profile
    )
    if acts_profile and "config" in acts_profile:
        apply_profile_to_config(config.analysis.acts, acts_profile["config"])
    env_acts_model = os.getenv("TRANSCRIPTX_ACTS_MODEL")
    if env_acts_model:
        config.analysis.acts.ml_model_name = env_acts_model

    tag_profile = profile_manager.load_profile(
        "tag_extraction", config.analysis.active_tag_extraction_profile
    )
    if tag_profile and "config" in tag_profile:
        apply_profile_to_config(config.analysis.tag_extraction, tag_profile["config"])

    qa_profile = profile_manager.load_profile(
        "qa_analysis", config.analysis.active_qa_analysis_profile
    )
    if qa_profile and "config" in qa_profile:
        apply_profile_to_config(config.analysis.qa_analysis, qa_profile["config"])

    temporal_profile = profile_manager.load_profile(
        "temporal_dynamics", config.analysis.active_temporal_dynamics_profile
    )
    if temporal_profile and "config" in temporal_profile:
        apply_profile_to_config(
            config.analysis.temporal_dynamics, temporal_profile["config"]
        )

    vector_profile = profile_manager.load_profile(
        "vectorization", config.analysis.active_vectorization_profile
    )
    if vector_profile and "config" in vector_profile:
        apply_profile_to_config(config.analysis.vectorization, vector_profile["config"])

    workflow_profile = profile_manager.load_profile(
        "workflow", config.active_workflow_profile
    )
    if workflow_profile and "config" in workflow_profile:
        apply_profile_to_config(config.workflow, workflow_profile["config"])
