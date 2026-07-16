"""Offline unit tests for semantic similarity visualization helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.semantic_similarity import visualization as viz


@pytest.mark.unit
def test_create_visualizations_advanced_full_path() -> None:
    service = MagicMock()
    service.save_chart.return_value = {"static": "/tmp/chart.png"}
    results = {
        "summary": {
            "speaker_statistics": {
                "Alice": {"repetitions": 2, "average_similarity": 0.8},
                "Bob": {"repetitions": 1, "average_similarity": 0.6},
            },
            "agreement_disagreement_breakdown": {"agreement": 3, "echo": 1},
        },
        "speaker_repetitions": {
            "Alice": [{"similarity": 0.9}, {"similarity": 0.7}],
            "Bob": [{"similarity": 0.55}],
        },
        "cross_speaker_repetitions": [{"similarity": 0.65}],
    }
    with patch.object(viz, "log_info"), patch.object(viz, "log_error"):
        paths = viz.create_visualizations_advanced(
            results, service, "base", "SEMANTIC"
        )
    assert len(paths) >= 3
    assert service.save_chart.call_count >= 3


@pytest.mark.unit
def test_create_visualizations_advanced_error_returns_empty() -> None:
    service = MagicMock()
    service.save_chart.side_effect = RuntimeError("fail")
    results = {
        "summary": {
            "speaker_statistics": {
                "Alice": {"repetitions": 1, "average_similarity": 0.5}
            }
        }
    }
    with patch.object(viz, "log_error") as log_err, patch.object(viz, "log_info"):
        paths = viz.create_visualizations_advanced(
            results, service, "base", "SEMANTIC"
        )
    assert paths == []
    log_err.assert_called()


@pytest.mark.unit
def test_create_visualizations_basic_full_path() -> None:
    service = MagicMock()
    service.save_chart.return_value = {"static": "/tmp/b.png"}
    results = {
        "summary": {
            "speaker_repetition_frequency": {"Alice": 2, "Unknown": 9, "Bob": 1},
            "agreement_breakdown": {"agreement": 2, "disagreement": 1},
        },
        "speaker_repetitions": {
            "Alice": [{"similarity": 0.8}, {"similarity": 0.7}],
            "Bob": [{"similarity": 0.6}],
        },
        "cross_speaker_repetitions": [{"similarity": 0.5}],
    }
    with patch.object(viz, "log_error"):
        paths = viz.create_visualizations_basic(
            results, service, "session", "SEMANTIC"
        )
    assert len(paths) >= 2


@pytest.mark.unit
def test_create_visualizations_basic_error_path() -> None:
    service = MagicMock()
    # Missing keys triggers exception in similarities loop
    results = {"summary": {"speaker_repetition_frequency": {"Alice": 1}}}
    with patch.object(viz, "log_error") as log_err:
        paths = viz.create_visualizations_basic(
            results, service, "base", "SEMANTIC"
        )
    assert paths == []
    log_err.assert_called()
