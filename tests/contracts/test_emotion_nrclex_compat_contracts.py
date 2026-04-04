"""Contract regressions for NRCLex compatibility behavior."""

from __future__ import annotations

import sys
import types

from transcriptx.core.analysis import emotion as emotion_module


class TestEmotionNrclexCompatibilityContracts:
    """Ensure emotion module supports multiple NRCLex score shapes."""

    def test_extract_scores_accepts_affect_frequencies_alias(self) -> None:
        class _FakeEmotion:
            affect_frequencies = {"joy": 0.6, "anticip": 0.4, "unknown": 0.9}

        scores = emotion_module._extract_nrc_emotion_scores(_FakeEmotion())
        assert scores == {"joy": 0.6, "anticipation": 0.4}

    def test_load_nrclex_works_without_raw_emotion_scores(self, monkeypatch) -> None:
        class _FakeNRCLexResult:
            def __init__(self, text: str):
                self.text = text
                self.affect_frequencies = {"joy": 1.0}

        fake_nrclex_module = types.SimpleNamespace(NRCLex=_FakeNRCLexResult)
        monkeypatch.setitem(sys.modules, "nrclex", fake_nrclex_module)

        def _fail_if_called() -> None:
            raise AssertionError("should not attempt TextBlob corpora download")

        monkeypatch.setattr(emotion_module, "_ensure_textblob_corpora", _fail_if_called)

        loaded = emotion_module._load_nrclex()
        assert loaded is _FakeNRCLexResult

    def test_nrclex_analyze_modern_load_raw_text_path(self) -> None:
        """nrclex 3+/4+ passes text via load_raw_text, not the constructor."""

        class _ModernFake:
            def __init__(self) -> None:
                self.loaded: str | None = None
                self.affect_frequencies = {"joy": 1.0}

            def load_raw_text(self, text: str) -> None:
                self.loaded = text

        inst = emotion_module._nrclex_analyze(_ModernFake, "hello world")
        scores = emotion_module._extract_nrc_emotion_scores(inst)
        assert scores == {"joy": 1.0}
        assert inst.loaded == "hello world"
