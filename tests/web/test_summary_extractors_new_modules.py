"""Unit tests for 0.3.4 summary extractors (lexical diversity + action items)."""

from __future__ import annotations

import pytest

from transcriptx.web.summary_extractors import get_extractor, has_extractor


@pytest.mark.unit
def test_lexical_diversity_and_action_items_extractors_registered() -> None:
    assert has_extractor("lexical_diversity")
    assert has_extractor("llm_action_items")


@pytest.mark.unit
def test_lexical_diversity_extractor_metrics_and_mtld_na() -> None:
    extractor = get_extractor("lexical_diversity")
    assert extractor is not None
    summary: dict = {"key_metrics": {}, "highlights": []}
    extractor(
        {
            "global_stats": {
                "ttr": 0.5123,
                "hapax_rate": 0.25,
                "token_count": 40,
            }
        },
        summary,
    )
    assert summary["key_metrics"]["Global TTR"] == "0.512"
    assert summary["key_metrics"]["Global hapax rate"] == "0.250"
    assert summary["key_metrics"]["Global MTLD"] == "n/a (short input)"
    assert any("length-sensitive" in h for h in summary["highlights"])

    summary2: dict = {"key_metrics": {}, "highlights": []}
    extractor({"lexical_diversity_global_stats": {"mtld": 12.34}}, summary2)
    assert summary2["key_metrics"]["Global MTLD"] == "12.3"

    # Non-dict global stats → no-op
    summary3: dict = {"key_metrics": {}, "highlights": []}
    extractor({"global_stats": []}, summary3)
    assert summary3["key_metrics"] == {}


@pytest.mark.unit
def test_llm_action_items_extractor_counts_by_status() -> None:
    extractor = get_extractor("llm_action_items")
    assert extractor is not None
    summary: dict = {"key_metrics": {}, "highlights": []}
    extractor(
        {
            "items": [
                {"text": "a", "status": "open"},
                {"text": "b", "status": "done"},
                {"text": "c", "status": "open"},
                {"text": "d", "status": "unclear"},
                {"text": "e", "status": "other"},
                "skip",
            ]
        },
        summary,
    )
    assert summary["key_metrics"]["Meeting extracts"] == 5
    assert summary["key_metrics"]["Open items"] == 2
    assert summary["key_metrics"]["Done items"] == 1
    assert summary["key_metrics"]["Unclear items"] == 1

    summary2: dict = {"key_metrics": {}, "highlights": []}
    extractor({"items": "bad"}, summary2)
    assert summary2["key_metrics"] == {}
