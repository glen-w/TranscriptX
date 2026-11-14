"""P1: NER skips non-English metadata instead of running English spaCy silently."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis import language_routing
from transcriptx.core.analysis.language_routing import (
    collect_segment_languages,
    primary_language_subtag,
    resolve_transcript_language,
    spacy_model_for_language,
)
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


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("  ", None),
        ("en-US", "en"),
        ("pt_BR", "pt"),
        ("FR", "fr"),
        ("auto", None),
        ("Unknown", None),
    ],
)
def test_primary_language_subtag(raw, expected) -> None:
    assert primary_language_subtag(raw) == expected


@pytest.mark.unit
def test_normalize_language_code_keeps_region_and_drops_auto() -> None:
    assert language_routing.normalize_language_code(" EN-us ") == "en-us"
    assert language_routing.normalize_language_code("auto") is None
    assert language_routing.normalize_language_code("unknown") is None


@pytest.mark.unit
def test_collect_segment_languages_sorted_unique_primary() -> None:
    segments = [
        {"language": "fr-CA"},
        {"language": "en_GB"},
        {"language": "fr"},
        {"text": "no language"},
        "not a mapping",
    ]
    assert collect_segment_languages(segments) == ["en", "fr"]


@pytest.mark.unit
def test_feature_modules_share_language_primitives() -> None:
    from transcriptx.core.analysis import lexicon_markers
    from transcriptx.core.analysis.emotion_family import language as emotion_language
    from transcriptx.core.analysis.topic_shift import language as topic_language
    from transcriptx.core.analysis.topic_shift import semantics

    assert topic_language.resolve_transcript_language is resolve_transcript_language
    assert lexicon_markers.resolve_transcript_language is resolve_transcript_language
    assert lexicon_markers.normalize_language_code is primary_language_subtag
    assert (
        emotion_language.normalize_language_code
        is language_routing.normalize_language_code
    )
    assert emotion_language.is_english is language_routing.is_english
    assert semantics.ENGLISH_CODES is language_routing.ENGLISH_CODES
    assert lexicon_markers.ENGLISH_CODES is language_routing.ENGLISH_CODES


@pytest.mark.unit
@pytest.mark.parametrize(
    ("segments", "metadata", "expected"),
    [
        ([{"language": "es"}], {"language": "en"}, ("es", "segment_language")),
        (
            [{"language": "en"}, {"language": "eng"}],
            None,
            ("en", "mixed_english_variants"),
        ),
        (
            [{"language": "fr"}, {"language": "en-GB"}],
            None,
            ("en", "mixed_segment_languages"),
        ),
        ([{"text": "hi"}], {"language": "pt_BR"}, ("pt", "transcript_metadata")),
        ([{"text": "hi"}], {}, ("en", "assumed_en_missing_metadata")),
        ([{"text": "hi"}], None, ("en", "assumed_en_missing_metadata")),
        # "auto"/"unknown" are placeholders, not languages.
        (
            [{"language": "auto"}],
            {"language": "auto"},
            ("en", "assumed_en_missing_metadata"),
        ),
        ([{"language": "unknown"}], {"language": "de"}, ("de", "transcript_metadata")),
    ],
)
def test_resolve_transcript_language(segments, metadata, expected) -> None:
    assert resolve_transcript_language(segments, metadata) == expected
