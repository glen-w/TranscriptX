"""Contracts for settings/knobs taxonomy honesty (Phase 0–1 cleanup)."""

from __future__ import annotations

import inspect

from transcriptx.core.config.gui_support import (
    COMMON_SETTINGS_SCHEMA,
    PROFILE_TARGET_CONTRACTS,
)
from transcriptx.core.utils.config.main import TranscriptXConfig


def test_transcriptx_config_init_docstring_matches_load_order() -> None:
    doc = inspect.getdoc(TranscriptXConfig.__init__) or ""
    lowered = doc.lower()
    assert "active module / workflow profiles" in lowered
    assert "environment variables" in lowered
    assert "wins" in lowered
    # Highest-priority claim must be env, not "env then file then defaults".
    env_idx = lowered.index("environment variables")
    file_idx = lowered.index("configuration file")
    assert file_idx < env_idx


def test_common_settings_legacy_semantics_group_labelled() -> None:
    legacy = [
        f
        for f in COMMON_SETTINGS_SCHEMA
        if f.key
        in {
            "analysis.semantic_similarity_threshold",
            "analysis.cross_speaker_similarity_threshold",
            "analysis.semantic_similarity_method",
        }
    ]
    assert len(legacy) == 3
    assert all("legacy" in f.group.lower() for f in legacy)


def test_semantic_profile_guided_fields_cover_common_nested_keys() -> None:
    guided = set(
        PROFILE_TARGET_CONTRACTS["semantic_similarity"].edit_support.guided_fields
    )
    nested_common = [
        f.key.split("analysis.semantic_similarity.", 1)[1]
        for f in COMMON_SETTINGS_SCHEMA
        if f.key.startswith("analysis.semantic_similarity.")
    ]
    missing = [k for k in nested_common if k not in guided]
    assert missing == []
