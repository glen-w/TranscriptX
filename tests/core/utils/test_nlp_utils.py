"""
Tests for NLP helper functions.

This module tests stopwords, tics, discourse stoplists, and preprocessing.

Characterization notes for a future nlp_utils split (no behavior change here):
- Hub sections: stopwords (load/get, lazy ALL_STOPWORDS), tics + discourse
  stoplists (masks, is_tic, extract_tics_from_text), preprocess variants
  (preprocess_for_analysis and the *_for_topic_modeling / _insight_eligibility /
  _sentiment / _similarity wrappers, tokenize_and_filter, has_meaningful_content).
- Known dead/unwired symbols: ``preprocess_for_insight_eligibility`` is defined
  but not imported anywhere in production (insight_eligibility/content_filter
  uses nlp_runtime.get_nlp_model directly); ``phrase_contains_masked_term`` has
  no production callers outside this module.
- The mocked-spaCy tests below are the regression gate for any extraction; they
  pin token-filtering semantics without requiring a downloaded spaCy model.
"""

from unittest.mock import patch


from transcriptx.core.utils.nlp_utils import (
    build_tic_mask,
    extract_tics_from_text,
    is_tic,
    load_custom_stopwords,
    load_discourse_stoplist,
    load_tic_phrases,
    phrase_contains_masked_term,
    preprocess_for_analysis,
    preprocess_for_insight_eligibility,
    preprocess_for_sentiment,
    preprocess_for_similarity,
    preprocess_for_topic_modeling,
    tokenize_and_filter,
    has_meaningful_content,
)


class _FakeToken:
    def __init__(
        self,
        text: str,
        pos: str = "NOUN",
        lemma: str | None = None,
        is_alpha: bool = True,
    ):
        self.text = text
        self.pos_ = pos
        self.lemma_ = lemma if lemma is not None else text
        self.is_alpha = is_alpha


class _FakeDoc:
    def __init__(self, tokens: list[_FakeToken], has_pos: bool = True):
        self._tokens = tokens
        self._has_pos = has_pos

    def __iter__(self):
        return iter(self._tokens)

    def has_annotation(self, _name: str) -> bool:
        return self._has_pos


def _fake_nlp(annotations: dict | None = None, has_pos: bool = True):
    """Whitespace-tokenizing fake spaCy pipeline with controlled annotations.

    annotations maps lowercase token text -> (pos, lemma, is_alpha); unmapped
    tokens default to NOUN / own lemma / str.isalpha().
    """
    annotations = annotations or {}

    def nlp(text: str) -> _FakeDoc:
        tokens = []
        for raw in text.split():
            pos, lemma, is_alpha = annotations.get(raw, ("NOUN", raw, raw.isalpha()))
            tokens.append(_FakeToken(raw, pos, lemma, is_alpha))
        return _FakeDoc(tokens, has_pos)

    return nlp


class TestLoadCustomStopwords:
    """Tests for load_custom_stopwords function."""

    def test_loads_stopwords_from_file(self, tmp_path):
        """Test that stopwords are loaded from file."""
        stopwords_file = tmp_path / "stopwords.json"
        stopwords_file.write_text('["word1", "word2", "word3"]')

        with patch("transcriptx.core.utils.nlp_utils.STOPWORDS_FILE", stopwords_file):
            stopwords = load_custom_stopwords()

            assert isinstance(stopwords, set)
            assert "word1" in stopwords
            assert "word2" in stopwords

    def test_returns_empty_set_when_file_not_exists(self, tmp_path):
        """Test that empty set is returned when file doesn't exist."""
        stopwords_file = tmp_path / "nonexistent.json"

        with patch("transcriptx.core.utils.nlp_utils.STOPWORDS_FILE", stopwords_file):
            stopwords = load_custom_stopwords()

            assert isinstance(stopwords, set)
            assert len(stopwords) == 0


class TestLoadTicPhrases:
    """Tests for load_tic_phrases function."""

    def test_loads_tic_phrases_from_file(self, tmp_path):
        """Test that tic phrases are loaded from file."""
        tics_file = tmp_path / "tics.json"
        tics_data = {"category1": ["um", "uh"], "category2": ["like", "you know"]}
        tics_file.write_text(str(tics_data).replace("'", '"'))

        with patch("transcriptx.core.utils.nlp_utils.TICS_FILE", tics_file):
            tics = load_tic_phrases()

            assert isinstance(tics, dict)
            assert "category1" in tics or len(tics) > 0

    def test_returns_empty_dict_when_file_not_exists(self, tmp_path):
        """Test that empty dict is returned when file doesn't exist."""
        tics_file = tmp_path / "nonexistent.json"

        with patch("transcriptx.core.utils.nlp_utils.TICS_FILE", tics_file):
            tics = load_tic_phrases()

            assert isinstance(tics, dict)


class TestIsTic:
    """Tests for is_tic function."""

    def test_identifies_tic_phrases(self):
        """Test that tic phrases are identified."""
        with patch(
            "transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", {"um", "uh", "like"}
        ):
            assert is_tic("um") is True
            assert is_tic("UM") is True  # Case insensitive
            assert is_tic("like") is True

    def test_rejects_non_tic_phrases(self):
        """Test that non-tic phrases are rejected."""
        with patch("transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", {"um", "uh"}):
            assert is_tic("hello") is False
            assert is_tic("world") is False


class TestExtractTicsFromText:
    """Tests for extract_tics_from_text function."""

    def test_extracts_tics_from_text(self):
        """Test that tics are extracted from text."""
        with patch(
            "transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", {"um", "uh", "like"}
        ):
            text = "Hello um world like this"
            tics = extract_tics_from_text(text)

            assert isinstance(tics, list)
            assert "um" in tics or "like" in tics

    def test_returns_empty_list_when_no_tics(self):
        """Test that empty list is returned when no tics found."""
        with patch("transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", {"um", "uh"}):
            text = "Hello world this is a test"
            tics = extract_tics_from_text(text)

            assert isinstance(tics, list)
            assert len(tics) == 0


class TestPreprocessForAnalysis:
    """Tests for preprocess_for_analysis function."""

    def test_preprocesses_text(self):
        """Test that text is preprocessed."""
        text = "Hello, world! This is a test."

        result = preprocess_for_analysis(text)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_handles_empty_text(self):
        """Test that empty text is handled."""
        result = preprocess_for_analysis("")

        assert isinstance(result, str)

    def test_removes_special_characters(self):
        """Test that special characters are handled."""
        text = "Hello!!! World??? Test---"

        result = preprocess_for_analysis(text)

        # Should process text (may remove or normalize special chars)
        assert isinstance(result, str)


class TestLoadDiscourseStoplist:
    """Tests for load_discourse_stoplist (same file-loading style as stopwords)."""

    def test_loads_discourse_stoplist_from_file(self, tmp_path):
        stoplist_file = tmp_path / "discourse.json"
        stoplist_file.write_text(
            '{"discourse_verbs": ["think", "say"], "hedge_terms": ["maybe"]}'
        )

        with patch(
            "transcriptx.core.utils.nlp_utils.DISCOURSE_STOPLIST_FILE", stoplist_file
        ):
            stoplist = load_discourse_stoplist()

        assert stoplist == {
            "discourse_verbs": ["think", "say"],
            "hedge_terms": ["maybe"],
        }

    def test_returns_empty_dict_when_file_not_exists(self, tmp_path):
        with patch(
            "transcriptx.core.utils.nlp_utils.DISCOURSE_STOPLIST_FILE",
            tmp_path / "nonexistent.json",
        ):
            assert load_discourse_stoplist() == {}


class TestBuildTicMask:
    """Golden tests for the unified style/discourse mask."""

    def test_mask_is_union_of_tics_and_discourse_stopwords(self):
        with (
            patch("transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", {"um", "uh"}),
            patch(
                "transcriptx.core.utils.nlp_utils.ALL_DISCOURSE_STOPWORDS",
                {"basically"},
            ),
        ):
            assert build_tic_mask() == {"um", "uh", "basically"}

    def test_extra_terms_are_lowercased_and_added(self):
        with (
            patch("transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", {"um"}),
            patch("transcriptx.core.utils.nlp_utils.ALL_DISCOURSE_STOPWORDS", set()),
        ):
            assert build_tic_mask({"FOO", "Bar"}) == {"um", "foo", "bar"}

    def test_phrase_contains_masked_term(self):
        mask = {"um", "basically"}
        assert phrase_contains_masked_term(["Hello", "UM"], mask) is True
        assert phrase_contains_masked_term(["hello", "world"], mask) is False


class TestTokenizeAndFilterMocked:
    """Golden tests for tokenize_and_filter with a mocked spaCy pipeline."""

    def test_filters_stopwords_tics_and_non_alpha(self):
        fake = _fake_nlp()
        with (
            patch("transcriptx.core.utils.nlp_utils._get_nlp_model", return_value=fake),
            patch(
                "transcriptx.core.utils.nlp_utils.get_all_stopwords",
                return_value={"the", "is"},
            ),
            patch("transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", {"um"}),
        ):
            tokens = tokenize_and_filter("The project um is great 123")
        assert tokens == ["project", "great"]

    def test_alpha_only_false_keeps_non_alpha_tokens(self):
        fake = _fake_nlp()
        with (
            patch("transcriptx.core.utils.nlp_utils._get_nlp_model", return_value=fake),
            patch(
                "transcriptx.core.utils.nlp_utils.get_all_stopwords",
                return_value=set(),
            ),
            patch("transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", set()),
        ):
            tokens = tokenize_and_filter("version 123", alpha_only=False)
        assert tokens == ["version", "123"]

    def test_empty_text_returns_empty_list(self):
        assert tokenize_and_filter("") == []
        assert tokenize_and_filter("   ") == []


class TestPreprocessForAnalysisMocked:
    """Golden tests for preprocess_for_analysis filtering semantics."""

    def test_stopword_and_tic_filtering(self):
        fake = _fake_nlp()
        with (
            patch("transcriptx.core.utils.nlp_utils._get_nlp_model", return_value=fake),
            patch(
                "transcriptx.core.utils.nlp_utils.get_all_stopwords",
                return_value={"the"},
            ),
            patch("transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", {"um"}),
        ):
            result = preprocess_for_analysis("The um budget report")
        assert result == "budget report"

    def test_content_words_only_uses_pos_annotations(self):
        annotations = {
            "she": ("PRON", "she", True),
            "quickly": ("ADV", "quickly", True),
            "reviewed": ("VERB", "review", True),
            "the": ("DET", "the", True),
            "budget": ("NOUN", "budget", True),
        }
        fake = _fake_nlp(annotations)
        with (
            patch("transcriptx.core.utils.nlp_utils._get_nlp_model", return_value=fake),
            patch(
                "transcriptx.core.utils.nlp_utils.get_all_stopwords",
                return_value=set(),
            ),
            patch("transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", set()),
        ):
            result = preprocess_for_analysis(
                "She quickly reviewed the budget", content_words_only=True
            )
        assert result == "quickly reviewed budget"

    def test_explicit_pos_filter_overrides_content_tags(self):
        annotations = {
            "run": ("VERB", "run", True),
            "fast": ("ADV", "fast", True),
            "race": ("NOUN", "race", True),
        }
        fake = _fake_nlp(annotations)
        with (
            patch("transcriptx.core.utils.nlp_utils._get_nlp_model", return_value=fake),
            patch(
                "transcriptx.core.utils.nlp_utils.get_all_stopwords",
                return_value=set(),
            ),
            patch("transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", set()),
        ):
            result = preprocess_for_analysis("run fast race", pos_filter={"NOUN"})
        assert result == "race"

    def test_pos_filter_disabled_when_pipeline_lacks_pos(self):
        annotations = {
            "she": ("", "she", True),
            "budget": ("", "budget", True),
        }
        fake = _fake_nlp(annotations, has_pos=False)
        with (
            patch("transcriptx.core.utils.nlp_utils._get_nlp_model", return_value=fake),
            patch(
                "transcriptx.core.utils.nlp_utils.get_all_stopwords",
                return_value=set(),
            ),
            patch("transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", set()),
        ):
            result = preprocess_for_analysis("she budget", content_words_only=True)
        # Tokenizer-only pipelines keep all tokens instead of dropping everything.
        assert result == "she budget"


class TestPreprocessVariantsMocked:
    """Golden tests for the preprocess_for_* variant contracts."""

    _ANNOTATIONS = {
        "i": ("PRON", "i", True),
        "think": ("VERB", "think", True),
        "the": ("DET", "the", True),
        "new": ("ADJ", "new", True),
        "budget": ("NOUN", "budget", True),
        "works": ("VERB", "work", True),
        "um": ("INTJ", "um", True),
    }

    def _patched(self, stopwords: set[str], tics: set[str]):
        fake = _fake_nlp(self._ANNOTATIONS)
        return (
            patch("transcriptx.core.utils.nlp_utils._get_nlp_model", return_value=fake),
            patch(
                "transcriptx.core.utils.nlp_utils.get_all_stopwords",
                return_value=stopwords,
            ),
            patch("transcriptx.core.utils.nlp_utils.ALL_VERBAL_TICS", tics),
        )

    def test_topic_modeling_keeps_content_words_only(self):
        p1, p2, p3 = self._patched({"the", "i"}, {"um"})
        with p1, p2, p3:
            result = preprocess_for_topic_modeling("I think the um new budget works")
        assert result == "think new budget works"

    def test_sentiment_keeps_stopwords_drops_tics(self):
        p1, p2, p3 = self._patched({"the", "i"}, {"um"})
        with p1, p2, p3:
            result = preprocess_for_sentiment("I think the um new budget works")
        assert result == "i think the new budget works"

    def test_similarity_drops_stopwords_keeps_all_pos(self):
        p1, p2, p3 = self._patched({"the", "i"}, {"um"})
        with p1, p2, p3:
            result = preprocess_for_similarity("I think the um new budget works")
        assert result == "think new budget works"

    def test_insight_eligibility_drops_discourse_verbs_by_lemma(self):
        p1, p2, p3 = self._patched({"the", "i"}, {"um"})
        with (
            p1,
            p2,
            p3,
            patch(
                "transcriptx.core.utils.nlp_utils.ALL_DISCOURSE_STOPWORDS",
                set(),
            ),
            patch(
                "transcriptx.core.utils.nlp_utils.DISCOURSE_VERBS",
                {"think"},
            ),
        ):
            result = preprocess_for_insight_eligibility(
                "I think the um new budget works"
            )
        # "think" dropped via discourse-verb lemma; "works" (lemma "work") kept.
        assert result == "new budget works"


class TestHasMeaningfulContent:
    """Contract tests for has_meaningful_content (preprocessing injected)."""

    def test_true_when_enough_words_remain(self):
        assert (
            has_meaningful_content("raw", preprocessing_func=lambda _t: "alpha beta")
            is True
        )

    def test_false_when_below_min_words(self):
        assert (
            has_meaningful_content(
                "raw", min_words=3, preprocessing_func=lambda _t: "alpha beta"
            )
            is False
        )

    def test_false_for_empty_or_filler_only_text(self):
        assert has_meaningful_content("", preprocessing_func=lambda _t: "x") is False
        assert (
            has_meaningful_content("um uh", preprocessing_func=lambda _t: "") is False
        )
