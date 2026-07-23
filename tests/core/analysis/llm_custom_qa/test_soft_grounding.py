"""Soft grounding: never kill answered rows for quote miss."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.analysis.llm_custom_qa.grounding import apply_soft_grounding


@pytest.mark.unit
def test_soft_grounding_keeps_answered_when_quotes_miss() -> None:
    corpus = SimpleNamespace(
        corpus_text="hello world from the meeting",
        entries=[],
        truncated=False,
    )
    # Minimal corpus that will not ground the quote
    from transcriptx.core.analysis.llm_custom_qa.bounded_input import (
        build_grounding_corpus,
    )

    corpus = build_grounding_corpus(
        [{"text": "hello world from the meeting", "start": 0.0, "end": 1.0}],
        max_corpus_chars=10_000,
    )
    answers = [
        {
            "status": "answered",
            "answer": "They greeted each other.",
            "reasoning": "Greeting is present.",
            "citations": [],
            "_model_quotes": ["this quote does not exist in transcript at all"],
            "grounding": {
                "quotes_requested": 1,
                "quotes_grounded": 0,
                "citations_emitted": 0,
                "citations_truncated": 0,
                "cross_segment_citations": 0,
            },
        }
    ]
    diagnostics: dict[str, int] = {}
    out = apply_soft_grounding(answers, corpus, diagnostics=diagnostics)
    assert out[0]["status"] == "answered"
    assert out[0]["answer"] == "They greeted each other."
    assert out[0]["citations"] == []
    assert int(diagnostics.get("soft_quote_drops", 0)) >= 1
