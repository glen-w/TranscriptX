"""Probe partial nested config loads for merge-vs-replace bugs."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

import pytest

from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into

_SUBTREE_PROBES: list[dict[str, str]] = [
    {
        "subtree": "corrections",
        "partial": {"consistency_similarity_threshold": 0.91},
        "sibling_path": "fuzzy_similarity_threshold",
    },
    {
        "subtree": "highlights",
        "partial": {"counts": {"cold_open_quotes": 7}},
        "sibling_path": "counts.total_highlights",
    },
    {
        "subtree": "summary",
        "partial": {"counts": {"theme_bullets": 8}},
        "sibling_path": "counts.tension_bullets",
    },
    {
        "subtree": "bertopic",
        "partial": {"min_topic_size": 8},
        "sibling_path": "top_n_words",
    },
    {
        "subtree": "pauses",
        "partial": {"min_long_pause_seconds": 3.0},
        "sibling_path": "percentile_long_pause",
    },
    {
        "subtree": "voice",
        "partial": {"deep_mode": False},
        "sibling_path": "enabled",
    },
    {
        "subtree": "echoes",
        "partial": {"lookback_seconds": 300.0},
        "sibling_path": "max_candidates",
    },
    {
        "subtree": "momentum",
        "partial": {"weights": {"novelty": 0.5}},
        "sibling_path": "weights.pause_rate",
    },
    {
        "subtree": "moments",
        "partial": {"weight_map": {"long_pause": 0.4}},
        "sibling_path": "weight_map.echo_burst",
    },
    {
        "subtree": "affect_tension",
        "partial": {"window_segments": 9},
        "sibling_path": "weight_posneg_mismatch",
    },
    {
        "subtree": "speaker_exemplars",
        "partial": {"count": 3},
        "sibling_path": "min_words",
    },
]


def _get_nested(obj: object, dotted: str) -> object:
    current = obj
    for segment in dotted.split("."):
        if isinstance(current, dict):
            current = current[segment]
        else:
            current = getattr(current, segment)
    return current


@pytest.mark.parametrize("probe", _SUBTREE_PROBES, ids=lambda p: p["subtree"])
def test_partial_nested_load_merges_without_replacing_siblings(
    probe: dict[str, str], tmp_path: Path
) -> None:
    cfg = TranscriptXConfig()
    before = asdict(getattr(cfg.analysis, probe["subtree"]))
    expected_sibling = _get_nested(
        getattr(cfg.analysis, probe["subtree"]), probe["sibling_path"]
    )

    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"analysis": {probe["subtree"]: probe["partial"]}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))

    subtree_obj = getattr(cfg.analysis, probe["subtree"])
    assert is_dataclass(type(subtree_obj)), probe["subtree"]
    after = asdict(subtree_obj)

    sibling = _get_nested(subtree_obj, probe["sibling_path"])
    assert sibling == expected_sibling
    assert after != before


def test_dict_field_shallow_merge_on_nested_dataclass(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    before_pause = cfg.analysis.momentum.weights["pause_rate"]
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"analysis": {"momentum": {"weights": {"novelty": 0.99}}}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))
    assert cfg.analysis.momentum.weights["novelty"] == 0.99
    assert cfg.analysis.momentum.weights["pause_rate"] == before_pause


def test_list_field_replace_not_element_merge(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"analysis": {"echoes": {"exclude_phrases": ["custom-only"]}}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))
    assert cfg.analysis.echoes.exclude_phrases == ["custom-only"]


def test_missing_config_file_is_noop(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    before = cfg.analysis.pauses.min_long_pause_seconds
    load_config_file_into(cfg, str(tmp_path / "does-not-exist.json"))
    assert cfg.analysis.pauses.min_long_pause_seconds == before


def test_quality_profiles_replacement_omission_and_tuples(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    assert "balanced" in cfg.analysis.quality_filtering_profiles
    payload = {
        "analysis": {
            "quality_filtering_profiles": {
                "only_custom": {
                    "description": "x",
                    "weights": {"length_optimal": 1.0},
                    "thresholds": {"length_optimal": [1, 2]},
                    "indicators": {},
                }
            }
        }
    }
    path = tmp_path / "q.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    load_config_file_into(cfg, str(path))
    assert "balanced" not in cfg.analysis.quality_filtering_profiles
    assert set(cfg.analysis.quality_filtering_profiles) == {"only_custom"}
    assert cfg.analysis.quality_filtering_profiles["only_custom"]["thresholds"][
        "length_optimal"
    ] == (1, 2)


def test_quality_file_replacement_accepts_extra_keys_without_pydantic_reject(
    tmp_path: Path,
) -> None:
    """File replacements must not be model_validate'd (would strip/reject extras)."""
    cfg = TranscriptXConfig()
    payload = {
        "analysis": {
            "quality_filtering_profiles": {
                "weird": {
                    "description": "x",
                    "weights": {},
                    "thresholds": {},
                    "indicators": {},
                    "extra_user_key": {"nested": True},
                }
            }
        }
    }
    path = tmp_path / "q.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    load_config_file_into(cfg, str(path))
    assert cfg.analysis.quality_filtering_profiles["weird"]["extra_user_key"] == {
        "nested": True
    }


def test_llm_summary_nested_partial_override(tmp_path: Path) -> None:
    """Single-field llm_* subtrees still accept nested file merge."""
    cfg = TranscriptXConfig()
    path = tmp_path / "c.json"
    path.write_text(
        json.dumps({"analysis": {"llm_summary": {"effort": "high"}}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    assert cfg.analysis.llm_summary.effort == "high"


def test_ui_presets_nested_partial_override(tmp_path: Path) -> None:
    """Project file can retarget Balanced LLM/heavy allowlists."""
    cfg = TranscriptXConfig()
    assert cfg.analysis.ui_presets.balanced.llm_module_ids == ["llm_summary"]
    path = tmp_path / "presets.json"
    path.write_text(
        json.dumps(
            {
                "analysis": {
                    "ui_presets": {
                        "balanced": {
                            "allow_llm": True,
                            "llm_module_ids": ["llm_summary", "llm_action_items"],
                            "heavy_module_ids": ["semantic_similarity_v2"],
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    assert cfg.analysis.ui_presets.balanced.llm_module_ids == [
        "llm_summary",
        "llm_action_items",
    ]
    assert cfg.analysis.ui_presets.balanced.heavy_module_ids == [
        "semantic_similarity_v2"
    ]
    # Unspecified presets keep defaults.
    assert cfg.analysis.ui_presets.quick.allow_llm is False
    assert cfg.analysis.ui_presets.thorough.include_excluded_from_default is True
