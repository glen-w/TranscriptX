"""Visibility, file-load roundtrip, and validation tests for analysis subtrees."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from transcriptx.core.config.registry import (
    build_registry,
    flatten,
    get_default_config_dict,
)
from transcriptx.core.config import validate_config
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into

_NEW_SUBTREES = (
    "corrections",
    "highlights",
    "summary",
    "bertopic",
    "pauses",
    "voice",
    "echoes",
    "momentum",
    "moments",
)

_SUBTREE_CASES: list[dict[str, Any]] = [
    {
        "subtree": "corrections",
        "partial": {"consistency_similarity_threshold": 0.91},
        "invalid_payload": {"consistency_similarity_threshold": "high"},
        "invalid_dotpath": "analysis.corrections.consistency_similarity_threshold",
    },
    {
        "subtree": "highlights",
        "partial": {"counts": {"cold_open_quotes": 7}},
        "invalid_payload": {"counts": {"cold_open_quotes": "many"}},
        "invalid_dotpath": "analysis.highlights.counts.cold_open_quotes",
    },
    {
        "subtree": "summary",
        "partial": {"counts": {"theme_bullets": 8}},
        "invalid_payload": {"counts": {"theme_bullets": "eight"}},
        "invalid_dotpath": "analysis.summary.counts.theme_bullets",
    },
    {
        "subtree": "bertopic",
        "partial": {"min_topic_size": 8},
        "invalid_payload": {"min_topic_size": "small"},
        "invalid_dotpath": "analysis.bertopic.min_topic_size",
    },
    {
        "subtree": "pauses",
        "partial": {"min_long_pause_seconds": 3.0},
        "invalid_payload": {"min_long_pause_seconds": "long"},
        "invalid_dotpath": "analysis.pauses.min_long_pause_seconds",
    },
    {
        "subtree": "voice",
        "partial": {"deep_mode": True},
        "invalid_payload": {"vad_mode": "loud"},
        "invalid_dotpath": "analysis.voice.vad_mode",
    },
    {
        "subtree": "echoes",
        "partial": {"lookback_seconds": 300.0},
        "invalid_payload": {"max_candidates": "lots"},
        "invalid_dotpath": "analysis.echoes.max_candidates",
    },
    {
        "subtree": "momentum",
        "partial": {"weights": {"novelty": 0.5}},
        "invalid_payload": {"weights": {"novelty": "heavy"}},
        "invalid_dotpath": "analysis.momentum.weights.novelty",
    },
    {
        "subtree": "moments",
        "partial": {"weight_map": {"long_pause": 0.4}},
        "invalid_payload": {"weight_map": {"long_pause": "strong"}},
        "invalid_dotpath": "analysis.moments.weight_map.long_pause",
    },
]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def test_new_analysis_subtrees_appear_in_default_config_dict() -> None:
    analysis = get_default_config_dict()["analysis"]
    for name in _NEW_SUBTREES:
        assert name in analysis, name
        assert isinstance(analysis[name], dict)


def test_new_analysis_subtrees_appear_in_registry() -> None:
    reg = build_registry()
    flat = flatten(get_default_config_dict())
    for name in _NEW_SUBTREES:
        prefix = f"analysis.{name}."
        assert any(key.startswith(prefix) for key in flat), name
        assert any(key.startswith(prefix) for key in reg), name


@pytest.mark.parametrize("case", _SUBTREE_CASES, ids=lambda c: c["subtree"])
def test_partial_file_load_roundtrip_merges_subtree(
    case: dict[str, Any], tmp_path: Path
) -> None:
    cfg = TranscriptXConfig()
    default_subtree = asdict(getattr(cfg.analysis, case["subtree"]))
    expected = _deep_merge(default_subtree, case["partial"])

    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"analysis": {case["subtree"]: case["partial"]}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))

    assert asdict(getattr(cfg.analysis, case["subtree"])) == expected


@pytest.mark.parametrize("case", _SUBTREE_CASES, ids=lambda c: c["subtree"])
def test_partial_payload_passes_validate_config(case: dict[str, Any]) -> None:
    errors = validate_config({"analysis": {case["subtree"]: case["partial"]}})
    prefix = f"analysis.{case['subtree']}"
    assert not any(key.startswith(prefix) for key in errors), errors


@pytest.mark.parametrize("case", _SUBTREE_CASES, ids=lambda c: c["subtree"])
def test_invalid_leaf_fails_validate_config(case: dict[str, Any]) -> None:
    errors = validate_config({"analysis": {case["subtree"]: case["invalid_payload"]}})
    assert case["invalid_dotpath"] in errors
