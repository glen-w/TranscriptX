"""EmotionAnalysis.analyze keeps the preflight envelope; scoring lives in _analyze_lexical."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.emotion import EmotionAnalysis
from transcriptx.core.analysis.emotion.preflight import LexicalPreflightResult


@pytest.mark.unit
def test_analyze_skips_lexical_when_preflight_fails(monkeypatch) -> None:
    module = EmotionAnalysis.__new__(EmotionAnalysis)
    lexical = MagicMock(return_value={"should_not": "run"})
    empty = MagicMock(return_value={"run_status": "skipped"})
    module._analyze_lexical = lexical
    module._empty_failed_result = empty
    monkeypatch.setattr(
        "transcriptx.core.analysis.emotion.run_lexical_preflight",
        lambda: LexicalPreflightResult(
            False, "lexical_preflight_failed", details={"error": "missing"}
        ),
    )

    out = module.analyze([])

    empty.assert_called_once()
    lexical.assert_not_called()
    assert out["run_status"] == "skipped"


@pytest.mark.unit
def test_analyze_delegates_to_lexical_after_preflight_ok(monkeypatch) -> None:
    module = EmotionAnalysis.__new__(EmotionAnalysis)
    preflight = LexicalPreflightResult(True, "ok", nrclex_version="3.0.0")
    lexical = MagicMock(return_value={"run_status": "ok", "peeled": True})
    module._analyze_lexical = lexical
    monkeypatch.setattr(
        "transcriptx.core.analysis.emotion.run_lexical_preflight",
        lambda: preflight,
    )

    out = module.analyze([{"id": "1", "text": "hello"}])

    lexical.assert_called_once()
    args, _kwargs = lexical.call_args
    assert args[0] == [{"id": "1", "text": "hello"}]
    assert args[2] is preflight
    assert out["peeled"] is True
    assert isinstance(args[1], str) and len(args[1]) == 32
