"""Store-specific consumer tests for mapping-store hydration."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.analysis.selection import apply_analysis_mode_settings
from transcriptx.core.analysis.semantic_similarity.config_resolve import (
    resolve_semantic_similarity_runtime,
)
from transcriptx.core.config.pydantic_bridge import PYDANTIC_REGISTRY_PILOTS
from transcriptx.core.utils.config import TranscriptXConfig, get_config, set_config
from transcriptx.core.utils.config.analysis import AnalysisConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into
from transcriptx.core.utils.config.profile_loading import apply_profile_to_config

from .delegation_test_utils import (
    assert_normalized_defaults_parity,
    assert_ownership_invariant_unchanged,
    without_transcriptx_env,
)


def test_mapping_stores_hydrate_from_models() -> None:
    assert_ownership_invariant_unchanged()
    with without_transcriptx_env():
        ac = AnalysisConfig()
    for pilot_id, attr in (
        ("quality_filtering_profiles", "quality_filtering_profiles"),
        ("semantic_similarity_profiles", "semantic_similarity_profiles"),
        ("quick_analysis_settings", "quick_analysis_settings"),
        ("full_analysis_settings", "full_analysis_settings"),
    ):
        spec = next(s for s in PYDANTIC_REGISTRY_PILOTS if s.pilot_id == pilot_id)
        assert_normalized_defaults_parity(getattr(ac, attr), spec.model().model_dump())


def test_quality_filtering_consumer_after_file_replacement(tmp_path: Path) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    default = cfg.get_quality_filtering_config()
    assert "weights" in default

    payload = {
        "analysis": {
            "quality_filtering_profiles": {
                "custom": {
                    "description": "custom",
                    "weights": {"length_optimal": 9.0},
                    "thresholds": {"length_optimal": [5, 40]},
                    "indicators": {"complex": ["therefore"]},
                }
            },
            "quality_filtering_profile": "custom",
        }
    }
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    load_config_file_into(cfg, str(path))
    # Replacement (not deep-merge): balanced gone unless present in payload
    assert "custom" in cfg.analysis.quality_filtering_profiles
    assert "balanced" not in cfg.analysis.quality_filtering_profiles
    assert isinstance(
        cfg.analysis.quality_filtering_profiles["custom"]["thresholds"][
            "length_optimal"
        ],
        tuple,
    )
    cfg.analysis.quality_filtering_profile = "custom"
    got = cfg.get_quality_filtering_config()
    assert got["weights"]["length_optimal"] == 9.0


def test_quality_unknown_selector_falls_back_to_balanced() -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    cfg.analysis.quality_filtering_profile = "does-not-exist"
    got = cfg.get_quality_filtering_config()
    assert (
        got["weights"] == cfg.analysis.quality_filtering_profiles["balanced"]["weights"]
    )


def test_quality_overrides_merge_into_consumer() -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    cfg.analysis.quality_filtering_profile = "balanced"
    cfg.analysis.quality_weights_override = {"length_optimal": 42.0}
    got = cfg.get_quality_filtering_config()
    assert got["weights"]["length_optimal"] == 42.0
    # Base profile dict not mutated
    assert (
        cfg.analysis.quality_filtering_profiles["balanced"]["weights"]["length_optimal"]
        != 42.0
    )


def test_full_analysis_settings_mode_consumer(tmp_path: Path) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
        set_config(cfg)
    path = tmp_path / "cfg.json"
    path.write_text(
        json.dumps(
            {
                "analysis": {
                    "full_analysis_settings": {
                        **cfg.analysis.full_analysis_settings,
                        "semantic_method": "simple",
                        "max_segments_for_semantic": 432,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    apply_analysis_mode_settings("full", profile="business")
    live = get_config()
    assert live.analysis.semantic_similarity_method == "simple"
    assert live.analysis.max_segments_for_semantic == 432
    assert live.analysis.quality_filtering_profile == "business"
    assert live.analysis.semantic_similarity.mode == "basic"


def test_ss_v2_preset_file_then_resolve(tmp_path: Path) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    path = tmp_path / "c.json"
    path.write_text(
        json.dumps(
            {
                "analysis": {
                    "active_semantic_similarity_profile": "fast",
                    "semantic_similarity_profiles": {
                        **cfg.analysis.semantic_similarity_profiles,
                        "fast": {
                            **cfg.analysis.semantic_similarity_profiles["fast"],
                            "top_k_per_segment": 7,
                        },
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    assert cfg.analysis.active_semantic_similarity_profile == "fast"
    resolved, _ = resolve_semantic_similarity_runtime(
        cfg.analysis, modules_in_run=set()
    )
    assert resolved.top_k_per_segment == 7
    assert resolved.self_similarity_threshold == 0.78


def test_quick_full_settings_mode_consumer(tmp_path: Path) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
        set_config(cfg)
    path = tmp_path / "cfg.json"
    path.write_text(
        json.dumps(
            {
                "analysis": {
                    "quick_analysis_settings": {
                        **cfg.analysis.quick_analysis_settings,
                        "semantic_method": "advanced",
                        "max_segments_for_semantic": 123,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    apply_analysis_mode_settings("quick")
    live = get_config()
    assert live.analysis.semantic_similarity_method == "advanced"
    assert live.analysis.max_segments_for_semantic == 123


def test_semantic_v2_presets_vs_adapter_target() -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    # Built-in preset path: active balanced overlays dataclass defaults (0.7 → 0.72).
    assert cfg.analysis.active_semantic_similarity_profile == "balanced"
    resolved, _ = resolve_semantic_similarity_runtime(
        cfg.analysis, modules_in_run=set()
    )
    assert resolved.self_similarity_threshold == 0.72
    assert resolved.top_k_per_segment == 50
    assert cfg.analysis.semantic_similarity.self_similarity_threshold == 0.7
    # Adapter-style mutation of dataclass target (not the presets dict)
    apply_profile_to_config(cfg.analysis.semantic_similarity, {"batch_size": 11})
    assert cfg.analysis.semantic_similarity.batch_size == 11
    # Preset dict unchanged by adapter target apply
    assert "balanced" in cfg.analysis.semantic_similarity_profiles


def test_mapping_store_kwargs_rejected() -> None:
    import pytest

    with pytest.raises(TypeError):
        AnalysisConfig(quality_filtering_profiles={})
