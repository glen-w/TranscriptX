"""Live apply_analysis_mode_settings against a real TranscriptXConfig."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.analysis.selection import apply_analysis_mode_settings
from transcriptx.core.utils.config import TranscriptXConfig, get_config, set_config
from transcriptx.core.utils.config.file_overrides import load_config_file_into

from .delegation_test_utils import without_transcriptx_env


def test_quick_mode_applies_presets_and_ss_v2_mode(tmp_path: Path) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
        set_config(cfg)
    path = tmp_path / "c.json"
    path.write_text(
        json.dumps(
            {
                "analysis": {
                    "quick_analysis_settings": {
                        **cfg.analysis.quick_analysis_settings,
                        "semantic_method": "advanced",
                        "max_segments_for_semantic": 321,
                        "ner_max_segments": 111,
                        "semantic_profile": "academic",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    apply_analysis_mode_settings("quick")
    live = get_config()
    assert live.analysis.analysis_mode == "quick"
    assert live.analysis.semantic_similarity_method == "advanced"
    assert live.analysis.max_segments_for_semantic == 321
    assert live.analysis.ner_max_segments == 111
    assert live.analysis.quality_filtering_profile == "academic"
    assert live.analysis.semantic_similarity.mode == "advanced"


def test_full_mode_applies_presets_profile_and_ss_v2_mode(tmp_path: Path) -> None:
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
        set_config(cfg)
    path = tmp_path / "c.json"
    path.write_text(
        json.dumps(
            {
                "analysis": {
                    "full_analysis_settings": {
                        **cfg.analysis.full_analysis_settings,
                        "semantic_method": "simple",
                        "max_segments_for_semantic": 777,
                        "max_segments_per_speaker": 333,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    apply_analysis_mode_settings("full", profile="technical")
    live = get_config()
    assert live.analysis.analysis_mode == "full"
    assert live.analysis.semantic_similarity_method == "simple"
    assert live.analysis.max_segments_for_semantic == 777
    assert live.analysis.max_segments_per_speaker == 333
    assert live.analysis.quality_filtering_profile == "technical"
    assert live.analysis.semantic_similarity.mode == "basic"
