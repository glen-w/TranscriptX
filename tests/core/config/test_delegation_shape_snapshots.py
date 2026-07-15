"""Pre-delegation shape snapshots for Batch 5 runtime delegation."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.analysis import AnalysisConfig

from .delegation_test_utils import without_transcriptx_env

FIXTURES = Path(__file__).resolve().parent / "fixtures"

_DELEGATION_SUBTREES = (
    "pauses",
    "voice",
    "corrections",
    "summary",
    "highlights",
    "llm_summary",
    "llm_speaker_summary",
    "llm_action_items",
)


def _normalize_for_json(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_normalize_for_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_for_json(v) for v in value]
    return value


def _subtree_shapes(subtree: str) -> dict:
    with without_transcriptx_env():
        return {
            "asdict": _normalize_for_json(asdict(getattr(AnalysisConfig(), subtree))),
            "to_dict": TranscriptXConfig().to_dict()["analysis"][subtree],
        }


def test_pre_delegation_subtree_shapes_match_fixtures() -> None:
    for subtree in _DELEGATION_SUBTREES:
        expected = json.loads(
            (FIXTURES / f"delegation_shape_{subtree}_pre.json").read_text()
        )
        assert _subtree_shapes(subtree) == expected


def test_pre_delegation_analysis_shape_matches_fixture() -> None:
    expected = json.loads((FIXTURES / "delegation_shape_analysis_pre.json").read_text())
    assert _normalize_for_json(asdict(AnalysisConfig())) == expected
