"""Characterization: failed file overrides leave the live config untouched (Config 1.7)."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import pytest

from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into


def _snapshot(cfg: TranscriptXConfig) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, value in vars(cfg).items():
        if name.startswith("_"):
            continue
        if is_dataclass(value):
            out[name] = asdict(value)
        else:
            out[name] = copy.deepcopy(value)
    return out


def test_failed_override_leaves_live_config_unchanged(tmp_path: Path) -> None:
    cfg = TranscriptXConfig()
    analysis_id = id(cfg.analysis)
    output_id = id(cfg.output)
    before = _snapshot(cfg)
    before_dynamic = cfg.output.dynamic_charts

    bad = tmp_path / "bad.json"
    # Invalid leaf that passes raw allowlist but fails complete validation.
    bad.write_text(
        json.dumps({"output": {"dynamic_charts": "sometimes"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Failed to load configuration"):
        load_config_file_into(cfg, str(bad))

    assert id(cfg.analysis) == analysis_id
    assert id(cfg.output) == output_id
    assert cfg.output.dynamic_charts == before_dynamic
    assert _snapshot(cfg) == before


def test_failed_nested_override_leaves_adapter_and_siblings_unchanged(
    tmp_path: Path,
) -> None:
    cfg = TranscriptXConfig()
    pauses_id = id(cfg.analysis.pauses)
    before_pauses = asdict(cfg.analysis.pauses)
    before_voice = asdict(cfg.analysis.voice)
    before_quality = copy.deepcopy(cfg.analysis.quality_filtering_profiles)

    bad = tmp_path / "bad_nested.json"
    # Force nested validate failure if pauses has validate; otherwise use invalid output.
    bad.write_text(
        json.dumps(
            {
                "analysis": {
                    "pauses": {"min_long_pause_seconds": 2.5},
                    "voice": {"deep_mode": False},
                },
                "output": {"dynamic_charts": "sometimes"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Failed to load configuration"):
        load_config_file_into(cfg, str(bad))

    assert id(cfg.analysis.pauses) == pauses_id
    assert asdict(cfg.analysis.pauses) == before_pauses
    assert asdict(cfg.analysis.voice) == before_voice
    assert cfg.analysis.quality_filtering_profiles == before_quality


def test_successful_override_commits_and_preserves_section_identity(
    tmp_path: Path,
) -> None:
    cfg = TranscriptXConfig()
    analysis_id = id(cfg.analysis)
    output_id = id(cfg.output)
    good = tmp_path / "good.json"
    good.write_text(
        json.dumps({"output": {"dynamic_charts": "on"}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(good))
    assert id(cfg.analysis) == analysis_id
    assert id(cfg.output) == output_id
    assert cfg.output.dynamic_charts == "on"
