from __future__ import annotations

import json
from typing import Any, Callable, Optional

from transcriptx.core.utils.config import STOPWORDS_FILE, TICS_FILE
from transcriptx.core.utils.notifications import notify_user
from transcriptx.core.utils.nlp_runtime import get_nlp_model


# --- Load extended stopwords ---
def load_custom_stopwords():
    path = STOPWORDS_FILE
    if not path.exists():
        notify_user(
            f"⚠️ Custom stopwords file not found: {STOPWORDS_FILE}",
            technical=True,
            section="ner",
        )
        return set()
    with open(path) as f:
        return set(json.load(f))


_custom_stopwords_cache: Optional[set[str]] = None
_all_stopwords_cache: Optional[set[str]] = None


class _LazyStopwords:
    def __contains__(self, item: str) -> bool:
        return item in get_all_stopwords()

    def __iter__(self):
        return iter(get_all_stopwords())

    def __len__(self) -> int:
        return len(get_all_stopwords())


class _LazyNLP:
    def __init__(self, loader: Callable[[], Any]) -> None:
        self._loader = loader

    def _get(self):
        return self._loader()

    def __call__(self, *args, **kwargs):
        return self._get()(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._get(), name)


def get_custom_stopwords() -> set[str]:
    global _custom_stopwords_cache
    if _custom_stopwords_cache is None:
        _custom_stopwords_cache = load_custom_stopwords()
    return _custom_stopwords_cache


def get_all_stopwords() -> set[str]:
    global _all_stopwords_cache
    if _all_stopwords_cache is None:
        from spacy.lang.en.stop_words import STOP_WORDS

        _all_stopwords_cache = STOP_WORDS.union(get_custom_stopwords())
    return _all_stopwords_cache


def _get_nlp_model():
    return get_nlp_model()


# Backward-compatible lazy exports
ALL_STOPWORDS = _LazyStopwords()
nlp = _LazyNLP(_get_nlp_model)


# --- Load structured tic phrases ---
def load_tic_phrases():
    path = TICS_FILE
    if not path.exists():
        notify_user(
            f"⚠️ Verbal tics file not found: {TICS_FILE}", technical=True, section="ner"
        )
        return {}
    with open(path) as f:
        return json.load(f)


VERBAL_TICS_BY_CATEGORY = load_tic_phrases()
ALL_VERBAL_TICS = set(
    phrase.lower() for phrases in VERBAL_TICS_BY_CATEGORY.values() for phrase in phrases
)


def is_tic(phrase):
    """Check if a word or phrase is in the tic list."""
    return phrase.lower() in ALL_VERBAL_TICS


def extract_tics_from_text(text: str) -> list:
    """Extract both single-word and multi-word tics from raw text."""
    lowered = text.lower()
    found = []
    for phrase in ALL_VERBAL_TICS:
        if phrase in lowered:
            found.append(phrase)
    return found


# --- Load flat tic list for compatibility ---
def load_tics() -> list:
    try:
        with open(TICS_FILE) as f:
            return json.load(f)
    except Exception as e:
        notify_user(
            f"⚠️ Could not load tics from {TICS_FILE}: {e}",
            technical=True,
            section="ner",
        )
        return []


# --- Centralized Text Preprocessing Functions ---


def preprocess_for_analysis(
    text: str,
    filter_stopwords: bool = True,
    filter_tics: bool = True,
    content_words_only: bool = False,
    pos_filter: set[str] | None = None,
) -> str:
    """
    Universal text preprocessing using spaCy.

    Args:
        text: Raw text to preprocess
        filter_stopwords: Remove stopwords from ALL_STOPWORDS
        filter_tics: Remove verbal tics from ALL_VERBAL_TICS
        content_words_only: Keep only nouns, verbs, adjectives, adverbs
        pos_filter: Optional specific POS tags to keep (e.g., {'NOUN', 'VERB'})

    Returns:
        Preprocessed text string
    """
    if not text or not text.strip():
        return ""

    # Process with spaCy
    doc = _get_nlp_model()(text.lower())

    # Define content word POS tags
    content_tags = {
        "NOUN",
        "PROPN",  # Nouns
        "VERB",
        "AUX",  # Verbs
        "ADJ",  # Adjectives
        "ADV",  # Adverbs
    }

    # Use provided pos_filter or content_tags if content_words_only is True
    if pos_filter is not None:
        allowed_tags = pos_filter
    elif content_words_only:
        allowed_tags = content_tags
    else:
        allowed_tags = None  # No POS filtering

    # Filter tokens
    filtered_tokens = []
    for token in doc:
        # Skip if not alphabetic
        if not token.is_alpha:
            continue

        # Skip if it's a stopword and filtering is enabled
        if filter_stopwords and token.text in get_all_stopwords():
            continue

        # Skip if it's a tic and filtering is enabled
        if filter_tics and token.text in ALL_VERBAL_TICS:
            continue

        # Skip if POS filtering is enabled and token doesn't match
        if allowed_tags is not None and token.pos_ not in allowed_tags:
            continue

        filtered_tokens.append(token.text)

    return " ".join(filtered_tokens)


def tokenize_and_filter(
    text: str,
    filter_stopwords: bool = True,
    filter_tics: bool = True,
    alpha_only: bool = True,
) -> list[str]:
    """
    Tokenize and filter text using spaCy.
    Returns list of tokens (replaces wordclouds version).

    Args:
        text: Raw text to tokenize and filter
        filter_stopwords: Remove stopwords from ALL_STOPWORDS
        filter_tics: Remove verbal tics from ALL_VERBAL_TICS
        alpha_only: Keep only alphabetic tokens

    Returns:
        List of filtered tokens
    """
    if not text or not text.strip():
        return []

    doc = _get_nlp_model()(text.lower())
    tokens = []

    for token in doc:
        # Skip if not alphabetic and alpha_only is True
        if alpha_only and not token.is_alpha:
            continue

        # Skip if it's a stopword and filtering is enabled
        if filter_stopwords and token.text in get_all_stopwords():
            continue

        # Skip if it's a tic and filtering is enabled
        if filter_tics and token.text in ALL_VERBAL_TICS:
            continue

        tokens.append(token.text)

    return tokens


def preprocess_for_topic_modeling(text: str) -> str:
    """
    Preprocessing optimized for topic modeling.
    Removes stopwords, tics, keeps only content words (NOUN, VERB, ADJ, ADV).

    Args:
        text: Raw text to preprocess

    Returns:
        Preprocessed text string suitable for topic modeling
    """
    return preprocess_for_analysis(
        text, filter_stopwords=True, filter_tics=True, content_words_only=True
    )


def preprocess_for_sentiment(text: str) -> str:
    """
    Preprocessing optimized for sentiment analysis.
    Removes tics but keeps stopwords (important for sentiment).

    Args:
        text: Raw text to preprocess

    Returns:
        Preprocessed text string suitable for sentiment analysis
    """
    return preprocess_for_analysis(
        text,
        filter_stopwords=False,  # Keep stopwords for sentiment
        filter_tics=True,
        content_words_only=False,
    )


def preprocess_for_similarity(text: str) -> str:
    """
    Preprocessing optimized for semantic similarity analysis.
    Removes stopwords and tics but keeps all content words.

    Args:
        text: Raw text to preprocess

    Returns:
        Preprocessed text string suitable for similarity analysis
    """
    return preprocess_for_analysis(
        text,
        filter_stopwords=True,
        filter_tics=True,
        content_words_only=False,  # Keep all word types for better embeddings
    )


def has_meaningful_content(
    text: str,
    min_words: int = 2,
    preprocessing_func: Callable[[str], str] = preprocess_for_similarity,
) -> bool:
    """
    Check if a text segment has meaningful content after preprocessing.

    This function preprocesses text (removing filler words/tics) and checks
    if enough meaningful words remain. Useful for filtering out segments
    that are mostly filler before expensive operations.

    Args:
        text: Raw text to check
        min_words: Minimum number of words required after preprocessing (default: 2)
        preprocessing_func: Function to preprocess text (default: preprocess_for_similarity)

    Returns:
        True if text has meaningful content, False otherwise

    Examples:
        >>> has_meaningful_content("um, uh, like, you know")  # False
        >>> has_meaningful_content("I think we should consider this")  # True
        >>> has_meaningful_content("um, I think we should", min_words=3)  # True
    """
    if not text or not text.strip():
        return False

    preprocessed = preprocessing_func(text)
    if not preprocessed:
        return False

    word_count = len(preprocessed.split())
    return word_count >= min_words
