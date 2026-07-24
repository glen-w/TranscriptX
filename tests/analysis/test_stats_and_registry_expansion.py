"""Analysis module contract expansions (offline, no models)."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.stats import StatsAnalysis
from transcriptx.core.pipeline.module_registry import (
    get_available_modules,
    get_module_info,
)


@pytest.mark.unit
def test_registry_includes_stats_and_unique() -> None:
    modules = get_available_modules()
    assert "stats" in modules
    assert len(modules) == len(set(modules))


@pytest.mark.unit
def test_stats_module_info_contract() -> None:
    info = get_module_info("stats")
    assert info is not None
    assert getattr(info, "name", None) == "stats" or "stats" in str(info)


@pytest.mark.unit
def test_stats_analyze_two_speakers_has_counts() -> None:
    segments = [
        {"speaker": "A", "text": "Hello there friend", "start": 0.0, "end": 1.0},
        {"speaker": "B", "text": "Hi again today", "start": 1.0, "end": 2.5},
    ]
    result = StatsAnalysis().analyze(segments)
    assert isinstance(result, dict)
    assert "speaker_stats" in result
    assert len(result["speaker_stats"]) >= 1


@pytest.mark.unit
def test_stats_rejects_empty_via_validate() -> None:
    analyzer = StatsAnalysis()
    assert analyzer.validate_input(
        [{"speaker": "A", "text": "x", "start": 0, "end": 1}]
    )
    assert analyzer.validate_input([]) is False
