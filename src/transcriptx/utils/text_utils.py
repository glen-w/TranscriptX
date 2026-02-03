"""
Text processing utilities for TranscriptX.

This module provides common text processing and formatting functions
used across the TranscriptX codebase.
"""

import re

# Lazy import to avoid startup delays
# import nltk
# from nltk.corpus import stopwords


def is_named_speaker(name: str) -> bool:
    """
    Determine if a speaker name is a human-annotated name.

    This function filters out system-generated or placeholder speaker names
    to focus analysis on actual human speakers. It identifies common patterns
    used by transcription systems for unidentified speakers.

    Args:
        name: Speaker name string to validate

    Returns:
        bool: True if the name appears to be a real person's name

    Examples:
        >>> is_named_speaker("John Smith")
        True
        >>> is_named_speaker("SPEAKER_01")
        False
        >>> is_named_speaker("Unidentified Speaker")
        False
        >>> is_named_speaker("Unknown")
        False
        >>> is_named_speaker("")
        False

    Note:
        This is used throughout the analysis pipeline to filter segments
        and generate reports that focus on meaningful speaker interactions.

        Common patterns that are filtered out:
        - "SPEAKER_01", "SPEAKER_02", etc. (system-generated IDs)
        - "Unidentified Speaker" (transcription system placeholders)
        - "Unknown" (generic unknown speaker labels)
        - Empty strings or whitespace-only names

        This filtering ensures that analysis results focus on actual
        human speakers rather than system artifacts.
    """
    if not name:
        return False

    name = name.strip().lower()

    # Check for system-generated names
    system_patterns = [
        r"^speaker_\d+$",
        r"^speaker\s*\d+",  # "Speaker 10", "Speaker_10 (Speaker_10)"
        r"^\d+$",  # pure numeric placeholder, e.g. "10"
        r"^unidentified.*$",
        r"^unknown$",
        r"^unknown_speaker$",
        r"^unknown.*speaker$",
        r"^none$",
        r"^$",
    ]

    for pattern in system_patterns:
        if re.match(pattern, name):
            return False

    return True


def format_time(seconds: float) -> str:
    """
    Format a float number of seconds into M:SS format for display.

    This function converts seconds into a human-readable time format
    suitable for display in logs, reports, and CLI output. It handles
    both integer and fractional seconds by truncating to whole seconds.

    Args:
        seconds: Number of seconds (float)

    Returns:
        str: Formatted time string in M:SS format (e.g., '3:45')

    Examples:
        >>> format_time(125.7)
        '2:05'
        >>> format_time(65.0)
        '1:05'
        >>> format_time(30.0)
        '0:30'

    Note:
        This function is used throughout TranscriptX for displaying:
        - Audio timestamps in transcripts
        - Processing durations in logs
        - Time-based analysis results
        - Progress indicators with time estimates
    """
    if seconds < 0:
        # Handle negative values correctly
        abs_seconds = abs(seconds)
        minutes = int(abs_seconds) // 60
        seconds_remainder = int(abs_seconds) % 60
        return f"-{minutes}:{seconds_remainder:02d}"

    minutes = int(seconds) // 60
    seconds_remainder = int(seconds) % 60
    return f"{minutes}:{seconds_remainder:02d}"


def format_time_detailed(seconds: float) -> str:
    """
    Formats a float number of seconds into H:MM:SS format.

    Args:
        seconds: Number of seconds

    Returns:
        Formatted time string in H:MM:SS format
    """
    if seconds < 0:
        return "0:00:00"

    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    seconds_remainder = int(seconds) % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds_remainder:02d}"
    return f"{minutes}:{seconds_remainder:02d}"


def clean_text(text: str) -> str:
    """
    Clean and normalize text for analysis.

    Args:
        text: Raw text to clean

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text.strip())

    # Remove common transcription artifacts
    text = re.sub(r"\[.*?\]", "", text)  # Remove bracketed text
    text = re.sub(r"\(.*?\)", "", text)  # Remove parenthetical text

    return text


def extract_sentences(text: str) -> list[str]:
    """
    Extract sentences from text using basic punctuation rules.

    Args:
        text: Text to split into sentences

    Returns:
        List of sentences
    """
    if not text:
        return []

    # Basic sentence splitting (can be improved with NLTK)
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    return sentences


def count_words(text: str) -> int:
    """
    Count words in text.

    Args:
        text: Text to count words in

    Returns:
        Number of words
    """
    if not text:
        return 0

    # Split on whitespace and filter out empty strings
    words = [word for word in text.split() if word.strip()]
    return len(words)


def extract_hashtags(text: str) -> list[str]:
    """
    Extract hashtags from text.

    Args:
        text: Text to extract hashtags from

    Returns:
        List of hashtags (without the # symbol)
    """
    if not text:
        return []

    hashtags = re.findall(r"#(\w+)", text)
    return hashtags


def extract_mentions(text: str) -> list[str]:
    """
    Extract @mentions from text.

    Args:
        text: Text to extract mentions from

    Returns:
        List of mentions (without the @ symbol)
    """
    if not text:
        return []

    mentions = re.findall(r"@(\w+)", text)
    return mentions


def normalize_speaker_name(name: str) -> str:
    """
    Normalize speaker names for consistent comparison.

    Args:
        name: Raw speaker name

    Returns:
        Normalized speaker name
    """
    if not name:
        return "Unknown"

    # Remove common prefixes/suffixes
    name = re.sub(r"^(mr\.|mrs\.|ms\.|dr\.)\s*", "", name.lower())
    name = re.sub(r"\s+", " ", name.strip())

    # Capitalize first letter of each word
    name = " ".join(word.capitalize() for word in name.split())

    return name


def is_valid_filename(filename: str) -> bool:
    """
    Check if a filename is valid for the current operating system.

    Args:
        filename: Filename to check

    Returns:
        True if the filename is valid
    """
    if not filename:
        return False

    # Check for invalid characters
    invalid_chars = '<>:"/\\|?*'
    return not any(char in filename for char in invalid_chars)


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    Sanitize a filename by replacing invalid characters.

    Args:
        filename: Filename to sanitize
        replacement: Character to replace invalid characters with

    Returns:
        Sanitized filename
    """
    if not filename:
        return ""

    # Replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, replacement)

    # Remove leading/trailing spaces and dots
    filename = filename.strip(". ")

    return filename


def normalize_text(text: str) -> str:
    """
    Normalize text for consistent processing and analysis.

    This function performs comprehensive text normalization including:
    - Unicode normalization with accent removal
    - Whitespace normalization
    - Case normalization
    - Punctuation removal

    Args:
        text: Raw text to normalize

    Returns:
        Normalized text
    """
    if not text:
        return ""

    import unicodedata

    # Unicode normalization and accent removal
    text = unicodedata.normalize("NFD", text)  # Decompose characters
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")  # Remove accents

    # Convert to lowercase for consistency
    text = text.lower()

    # Replace decimal points with spaces first
    text = re.sub(r"\.", " ", text)
    # Remove all other punctuation except spaces
    text = re.sub(r"[^\w\s]", "", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text.strip())

    return text.strip()


def get_combined_stopwords(
    tics_path: str = "preprocessing/stopwords/verbal_tics.json",
    stopwords_path: str | None = None,
) -> set:
    """
    DEPRECATED: Use transcriptx.core.utils.nlp_utils.ALL_STOPWORDS instead.

    Load and combine standard stopwords and tics/fillers from file(s).
    Optionally, add additional stopwords from a custom file.
    Args:
        tics_path: Path to tics/fillers JSON file.
        stopwords_path: Optional path to additional stopwords JSON file.
    Returns:
        Set of all stopwords and tics/fillers.
    """
    import warnings

    warnings.warn(
        "get_combined_stopwords is deprecated. Use transcriptx.core.utils.nlp_utils.ALL_STOPWORDS instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Redirect to the centralized version
    from transcriptx.core.utils.nlp_utils import ALL_STOPWORDS

    return ALL_STOPWORDS


def preprocess_text_for_topic_modeling(text: str, stopwords_set: set) -> str:
    """
    DEPRECATED: Use transcriptx.core.utils.nlp_utils.preprocess_for_topic_modeling instead.

    Remove stopwords/tics/fillers and keep only content words (nouns, verbs, adjectives, adverbs).
    Args:
        text: Input text to preprocess.
        stopwords_set: Set of stopwords/tics/fillers to remove.
    Returns:
        Preprocessed text string.
    """
    import warnings

    warnings.warn(
        "preprocess_text_for_topic_modeling is deprecated. Use transcriptx.core.utils.nlp_utils.preprocess_for_topic_modeling instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Redirect to the centralized version
    from transcriptx.core.utils.nlp_utils import (
        preprocess_for_topic_modeling as new_preprocess,
    )

    return new_preprocess(text)


def strip_emojis(text: str) -> str:
    """
    Remove all emoji characters from a string.

    This function uses regex to identify and remove emoji characters
    from text. It covers most emoji ranges including emoticons, symbols,
    transport symbols, flags, and various Unicode emoji blocks.

    Args:
        text: Input string that may contain emojis

    Returns:
        str: Input string with all emoji characters removed

    Examples:
        >>> strip_emojis("Hello 👋 world 🌍")
        'Hello  world '
        >>> strip_emojis("No emojis here")
        'No emojis here'

    Note:
        This is used when emojis are disabled in the configuration,
        ensuring that all output is emoji-free while preserving
        the original text content.
    """
    # This regex covers most emoji ranges (BMP and SMP)
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f1e0-\U0001f1ff"  # flags (iOS)
        "\U00002700-\U000027bf"  # Dingbats
        "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
        "\U00002600-\U000026ff"  # Misc symbols
        "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
        "\U000025a0-\U000025ff"  # Geometric Shapes
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)
