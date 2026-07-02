"""Unit tests for ConversationLoopsAnalysis module analyze path."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from transcriptx.core.analysis.conversation_loops import ConversationLoopsAnalysis


@pytest.mark.unit
@patch("transcriptx.core.analysis.conversation_loops.analysis.classify_utterance")
def test_conversation_loops_analysis_returns_patterns(mock_classify) -> None:
    mock_classify.side_effect = lambda text: "question" if "?" in text else "statement"
    segments = [
        {"speaker": "Alice", "text": "Can you help?", "start": 0.0, "end": 2.0},
        {"speaker": "Bob", "text": "Sure thing.", "start": 2.0, "end": 4.0},
        {"speaker": "Alice", "text": "Thanks!", "start": 4.0, "end": 5.0},
    ]
    result = ConversationLoopsAnalysis().analyze(segments)
    assert "loops" in result
    assert "conversation_loops" in result
    assert "summary" in result
    assert isinstance(result["loops"], list)
