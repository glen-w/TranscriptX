"""
Text processing utilities for TranscriptX.

This module provides common text processing and formatting functions
used across the TranscriptX codebase.
"""

import contextvars
import re
from typing import Any, Literal, Mapping

# Lazy import to avoid startup delays
# import nltk
# from nltk.corpus import stopwords

# Set by PipelineContext for the duration of a run so analysis eligibility
# helpers can treat diarized labels as speakers when ungated.
_pipeline_allow_unnamed_speakers: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "pipeline_allow_unnamed_speakers", default=False
)


def set_pipeline_allow_unnamed_speakers(value: bool) -> contextvars.Token[bool]:
    """Bind allow-unnamed for the current pipeline run (reset on context close)."""
    return _pipeline_allow_unnamed_speakers.set(bool(value))


def reset_pipeline_allow_unnamed_speakers(token: contextvars.Token[bool]) -> None:
    """Restore the previous allow-unnamed binding."""
    _pipeline_allow_unnamed_speakers.reset(token)


def get_pipeline_allow_unnamed_speakers() -> bool:
    """Return whether the active pipeline run allows unnamed/diarized speakers."""
    return bool(_pipeline_allow_unnamed_speakers.get())


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


def is_turn_taking_speaker_label(name: str) -> bool:
    """
    True when the label can identify a turn for interaction analysis (e.g. contagion).

    Unlike :func:`is_named_speaker`, diarization-style labels such as ``Speaker 1`` or
    ``SPEAKER_00`` are allowed. Bare unknown placeholders are excluded.
    """
    if not name:
        return False
    n = str(name).strip().lower()
    if not n:
        return False
    if n in {"none", "unidentified", "unidentified speaker"}:
        return False
    if re.match(r"^unknown(?:_speaker|\s+speaker)?$", n):
        return False
    return True


def is_analysis_speaker_label(
    name: str, *, allow_unnamed: bool | None = None
) -> bool:
    """
    True when a speaker label is eligible for analysis grouping.

    By default requires a human-named speaker. When ``allow_unnamed`` is True
    (or the active pipeline run is ungated), diarization labels such as
    ``SPEAKER_00`` are accepted via :func:`is_turn_taking_speaker_label`.
    """
    if allow_unnamed is None:
        allow_unnamed = get_pipeline_allow_unnamed_speakers()
    if allow_unnamed:
        return is_turn_taking_speaker_label(name)
    return is_named_speaker(name)


def is_eligible_named_speaker(
    display_name: str | None,
    speaker_id: str | None,
    ignored_ids: set[str] | None = None,
    *,
    allow_unnamed: bool | None = None,
) -> bool:
    """
    Return True when a speaker is eligible for per-speaker artifacts.

    This is the single blessed predicate for gating per-speaker charts/JSON/filenames.
    When ``allow_unnamed`` is True (or the active pipeline run is ungated),
    diarized labels count as eligible.
    """
    if not display_name or not speaker_id:
        return False
    if ignored_ids and (
        str(speaker_id) in ignored_ids or str(display_name) in ignored_ids
    ):
        return False
    if allow_unnamed is None:
        allow_unnamed = get_pipeline_allow_unnamed_speakers()
    if allow_unnamed:
        return is_turn_taking_speaker_label(str(display_name))
    return is_named_speaker(str(display_name))


def is_pipeline_eligible_speaker(
    display_name: str | None,
    speaker_id: str | None,
    ignored_ids: set[str] | None = None,
    *,
    allow_unnamed: bool = False,
) -> bool:
    """Explicit allow_unnamed variant of :func:`is_eligible_named_speaker`."""
    return is_eligible_named_speaker(
        display_name,
        speaker_id,
        ignored_ids,
        allow_unnamed=allow_unnamed,
    )


def is_runtime_eligible_speaker(
    display_name: str | None,
    speaker_id: str | None,
    runtime_flags: Mapping[str, Any] | None = None,
    ignored_ids: set[str] | None = None,
) -> bool:
    """Eligibility using ``runtime_flags['allow_unnamed_speakers']``."""
    flags = runtime_flags or {}
    ignored = ignored_ids
    if ignored is None:
        raw = flags.get("ignored_speaker_ids")
        if isinstance(raw, set):
            ignored = raw
        elif raw:
            ignored = {str(x) for x in raw}
    return is_pipeline_eligible_speaker(
        display_name,
        speaker_id,
        ignored,
        allow_unnamed=bool(flags.get("allow_unnamed_speakers")),
    )


def format_time(seconds: float) -> str:
    """
    Format a float number of seconds into M:SS format for display.

    This function converts seconds into a human-readable time format
    suitable for display in logs, reports, and plain-text output. It handles
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


def format_duration_display(
    seconds: float | int | None,
    *,
    hours_threshold_seconds: int = 3600,
    style: Literal["compact", "minutes_only"] = "compact",
) -> str:
    """Format duration for summary UI display in minutes or hours+minutes.

    Summary-style formatter for tables and metric cards. For clock timestamps
    (``2:05``, ``1:02:34``) use :func:`format_time` or
    ``RecordingsService.format_duration`` instead.

    Uses rounded whole minutes (``round(seconds / 60)``). Sub-minute positive
    durations display as ``1m``. In ``compact`` style, durations at or above
    *hours_threshold_seconds* render as ``Xh Ym``.

    Raw duration remains in seconds internally; this is display-only formatting.
    """
    if seconds is None:
        return "-"
    total_minutes = int(round(float(seconds) / 60.0))
    if seconds > 0 and total_minutes == 0:
        total_minutes = 1
    if style == "minutes_only" or float(seconds) < hours_threshold_seconds:
        return f"{total_minutes}m"
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m"


def format_duration_display_from_config(seconds: float | int | None) -> str:
    """Format duration using dashboard settings from :func:`get_config`."""
    try:
        from transcriptx.io.metadata_display_options import get_duration_display_options

        opts = get_duration_display_options()
        return format_duration_display(
            seconds,
            hours_threshold_seconds=opts.hours_threshold_seconds,
            style=opts.style,
        )
    except Exception:
        return format_duration_display(seconds)


def format_bytes_display(num_bytes: int | float | None) -> str:
    """Format a byte count with adaptive units (B / KB / MB / GB)."""
    try:
        value = int(num_bytes or 0)
    except (TypeError, ValueError):
        value = 0
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    if value < 1024 * 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    return f"{value / (1024 * 1024 * 1024):.2f} GB"


def compute_word_count_from_segments(segments) -> int:
    """Sum word counts across all segment text using :func:`count_words`."""
    total = 0
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        text = seg.get("text")
        if text is None:
            text = ""
        elif not isinstance(text, str):
            text = str(text)
        total += count_words(text)
    return total


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
