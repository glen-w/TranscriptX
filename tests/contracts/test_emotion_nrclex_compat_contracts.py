"""Contract regressions for NRCLex lexicon loading compatibility."""

from __future__ import annotations

from transcriptx.core.analysis.emotion.lexical_pipeline import (
    build_lexicon_from_nrclex,
)


class TestEmotionNrclexCompatibilityContracts:
    """Ensure lexical pipeline supports modern and legacy NRCLex shapes."""

    def test_build_lexicon_normalizes_anticip_alias(self) -> None:
        class _FakeNRCLex:
            AffectDict = {"happy": ["joy", "anticip"], "fearful": ["fear"]}

            def __init__(self, text: str = "") -> None:
                self.text = text
                self.lexicon = self.AffectDict

        lexicon = build_lexicon_from_nrclex(_FakeNRCLex)
        assert lexicon["happy"] == ["joy", "anticipation"]
        assert lexicon["fearful"] == ["fear"]

    def test_build_lexicon_modern_load_raw_text_path(self) -> None:
        """nrclex 3+/4+ constructs empty then load_raw_text."""

        class _ModernFake:
            AffectDict = {"joy": ["joy", "positive"]}

            def __init__(self) -> None:
                self.loaded: str | None = None
                self.lexicon = dict(self.AffectDict)

            def load_raw_text(self, text: str) -> None:
                self.loaded = text

        lexicon = build_lexicon_from_nrclex(_ModernFake)
        assert lexicon["joy"] == ["joy", "positive"]

    def test_build_lexicon_empty_source_returns_empty(self) -> None:
        class _Empty:
            def __init__(self, text: str = "") -> None:
                self.lexicon = {}

        assert build_lexicon_from_nrclex(_Empty) == {}
