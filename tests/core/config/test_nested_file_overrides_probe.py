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
