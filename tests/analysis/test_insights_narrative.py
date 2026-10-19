"""B18 insights_narrative module tests."""

from __future__ import annotations

from transcriptx.core.analysis.llm_support.insights_narrative_source import (
    build_narrative_input,
)
from transcriptx.core.analysis.insights_narrative import InsightsNarrativeAnalysis
from transcriptx.core.pipeline.module_registry import get_module_registry


def test_build_narrative_input_requires_ok_status() -> None:
    from transcriptx.core.analysis.highlights.post_process import stable_quote_id

    example = {
        "quote": "We must cut spend.",
        "start": 1.0,
        "end": 2.0,
        "speaker": "A",
    }
    qid = stable_quote_id(example, "t1")
    highlights = {
        "transcript_key": "t1",
        "themes": [
            {
                "label": "budget risk",
                "quote_ids": [qid],
            }
        ],
        "sections": {
            "cold_open": {"items": [example]},
            "emblematic_phrases": {"phrases": []},
        },
    }
    insights = {
        "status": "ok",
        "key_themes": [
            {
                "phrase": "budget risk",
                "evidence_quote_ids": [qid],
                "confidence": "high",
            }
        ],
        "recurring_ideas": [],
    }
    payload = build_narrative_input(insights, highlights)
    assert payload["key_themes"][0]["evidence"]


def test_insights_narrative_registered() -> None:
    info = get_module_registry().get_module_info("insights_narrative")
    assert info is not None
    assert info.requires_llm
    assert info.finalize_phase


def test_insights_narrative_skips_when_disabled(monkeypatch) -> None:
    from transcriptx.core.utils.config import get_config

    cfg = get_config()
    monkeypatch.setattr(cfg.analysis.insights, "narrative_enabled", False)

    class _Ctx:
        transcript_path = "x.json"

    result = InsightsNarrativeAnalysis().run_from_context(_Ctx())
    assert result["status"] == "skipped"
    assert result["metrics"]["skip_reason"] == "narrative_disabled"
