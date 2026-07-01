"""File-load roundtrip tests for top-level Pydantic settings pilots."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from transcriptx.core.config import validate_config
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into

_TOP_LEVEL_CASES: list[dict[str, Any]] = [
    {
        "section": "output",
        "attr": "output",
        "partial": {"dynamic_charts": "on"},
        "invalid_payload": {"dynamic_charts": "sometimes"},
        "invalid_dotpath": "output.dynamic_charts",
    },
    {
        "section": "input",
        "attr": "input",
        "partial": {"file_selection_mode": "direct"},
        "invalid_payload": {"file_selection_mode": "browse"},
        "invalid_dotpath": "input.file_selection_mode",
    },
    {
        "section": "logging",
        "attr": "logging",
        "partial": {"level": "DEBUG"},
        "invalid_payload": {"backup_count": "many"},
        "invalid_dotpath": "logging.backup_count",
    },
    {
        "section": "audio_preprocessing",
        "attr": "audio_preprocessing",
        "partial": {"normalize_mode": "off"},
        "invalid_payload": {"denoise_mode": "loud"},
        "invalid_dotpath": "audio_preprocessing.denoise_mode",
    },
    {
        "section": "workflow",
        "attr": "workflow",
        "partial": {"timeout_quick_seconds": 5400},
        "invalid_payload": {"timeout_quick_seconds": "slow"},
        "invalid_dotpath": "workflow.timeout_quick_seconds",
    },
    {
        "section": "group_analysis",
        "attr": "group_analysis",
        "partial": {"enabled": True},
        "invalid_payload": {"enabled": []},
        "invalid_dotpath": "group_analysis.enabled",
    },
    {
        "section": "metadata",
        "attr": "metadata",
        "partial": {"duration_calculation": "span"},
        "invalid_payload": {"duration_calculation": "total"},
        "invalid_dotpath": "metadata.duration_calculation",
    },
    {
        "section": "dashboard",
        "attr": "dashboard",
        "partial": {"duration_summary_style": "minutes_only"},
        "invalid_payload": {"duration_summary_style": "verbose"},
        "invalid_dotpath": "dashboard.duration_summary_style",
    },
    {
        "section": "llm",
        "attr": "llm",
        "partial": {"enabled": True},
        "invalid_payload": {"provider": "openai"},
        "invalid_dotpath": "llm.provider",
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


@pytest.mark.parametrize("case", _TOP_LEVEL_CASES, ids=lambda c: c["section"])
def test_partial_file_load_merges_top_level_section(
    case: dict[str, Any], tmp_path: Path
) -> None:
    cfg = TranscriptXConfig()
    section_obj = getattr(cfg, case["attr"])
    before = asdict(section_obj)
    expected = _deep_merge(before, case["partial"])

    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({case["section"]: case["partial"]}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))

    assert asdict(getattr(cfg, case["attr"])) == expected


@pytest.mark.parametrize("case", _TOP_LEVEL_CASES, ids=lambda c: c["section"])
def test_partial_top_level_payload_passes_validate_config(case: dict[str, Any]) -> None:
    errors = validate_config({case["section"]: case["partial"]})
    prefix = case["section"]
    assert not any(key.startswith(prefix) for key in errors), errors


@pytest.mark.parametrize("case", _TOP_LEVEL_CASES, ids=lambda c: c["section"])
def test_invalid_top_level_leaf_fails_validate_config(case: dict[str, Any]) -> None:
    errors = validate_config({case["section"]: case["invalid_payload"]})
    assert case["invalid_dotpath"] in errors
