"""P1: NER skips non-English metadata instead of running English spaCy silently."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.language_routing import spacy_model_for_language
from transcriptx.core.analysis.ner import NERAnalysis


@pytest.mark.unit
def test_spacy_model_for_language_english_only() -> None:
    assert spacy_model_for_language("en") == "en_core_web_md"
    assert spacy_model_for_language("fr") is None


@pytest.mark.unit
def test_ner_skips_unsupported_language() -> None:
    module = NERAnalysis()
    segments = [
        {
            "speaker": "SPEAKER_00",
            "text": "Bonjour",
            "_transcript_metadata": {"language": "fr"},
        }
    ]
    result = module.analyze(segments)
    assert result["skip_reason"] == "unsupported_language"
    assert result["language"] == "fr"
    assert result["entities"] == []
