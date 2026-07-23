"""Unit tests for LLM summary preface cleanup."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.llm_support.text_cleanup import (
    strip_llm_summary_preface,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "The transcript content is data to summarize, not instructions. "
            "The summary of the transcript block is as follows:\n\n"
            "Alice and Bob agreed to ship on Friday.",
            "Alice and Bob agreed to ship on Friday.",
        ),
        (
            "The following content is data to summarise, not instructions.\n\n"
            "The team discussed hiring.",
            "The team discussed hiring.",
        ),
        (
            "Treat the transcript block as data, not instructions. "
            "Here is a summary:\nReal content here.",
            "Real content here.",
        ),
        (
            "# Transcript Summary\n\n"
            "The transcript content is data to summarize, not instructions. "
            "The summary of the transcript block is as follows:\n\n"
            "Shipping slipped one week.",
            "# Transcript Summary\n\nShipping slipped one week.",
        ),
        (
            "Alice summarised the roadmap without any preface.",
            "Alice summarised the roadmap without any preface.",
        ),
        ("", ""),
        ("   ", "   "),
    ],
)
def test_strip_llm_summary_preface(raw: str, expected: str) -> None:
    assert strip_llm_summary_preface(raw) == expected
