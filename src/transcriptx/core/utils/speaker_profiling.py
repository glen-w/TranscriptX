"""
Speaker Profiling Utilities for TranscriptX.

This module provides comprehensive speaker analysis and profiling capabilities,
including long-term speaker tracking, behavioral fingerprinting, and speaker
registry management. It enables the system to build detailed profiles of
speakers across multiple conversations and sessions.

Key Features:
- Speaker profile persistence and management
- Behavioral fingerprinting using multiple metrics
- Speaker registry with caching
- Color assignment for visual identification
- Statistical analysis of speaking patterns
- Cross-session speaker tracking

The module analyzes various aspects of speaker behavior:
- Vocabulary and language patterns (TF-IDF analysis)
- Verbal tics and speech patterns
- Part-of-speech distribution
- Sentiment and emotion patterns
- Speaking rate and segment characteristics
- Named entity usage patterns

Speaker Profiling System:
The speaker profiling system creates persistent profiles that track speaker
behavior across multiple sessions. Each profile contains:
- Basic identification information
- Behavioral fingerprint data
- Historical session information
- Visual identification (colors)
- Statistical patterns and preferences

This enables advanced features like:
- Cross-session speaker recognition
- Behavioral pattern analysis
- Speaker-specific customization
- Long-term trend analysis
- Personalized analysis recommendations
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from transcriptx.core.analysis.emotion import compute_nrc_emotions
from transcriptx.core.analysis.ner import extract_named_entities
from transcriptx.core.utils.nlp_utils import ALL_STOPWORDS, extract_tics_from_text, nlp
from transcriptx.core.analysis.sentiment import score_sentiment

# Default directory for storing speaker profiles
# Profiles are stored as JSON files with speaker names as filenames
# This allows for easy backup, sharing, and version control of speaker data
from transcriptx.core.utils.paths import PROJECT_ROOT

SPEAKER_DIR = PROJECT_ROOT / "transcriptx_data" / "speakers"
SPEAKER_DIR.mkdir(parents=True, exist_ok=True)


def get_speaker_profile(name: str) -> dict[str, Any]:
    """
    Load or create a long-term speaker profile.

    This function manages persistent speaker profiles that are stored
    as JSON files. Each profile contains information about a speaker's
    behavior patterns, preferences, and history across multiple sessions.

    Args:
        name: Name of the speaker to load/create profile for

    Returns:
        Dictionary containing the speaker's profile data

    Note:
        If no profile exists for the speaker, a new one is created
        with default values and saved to disk. This ensures that
        every speaker has a profile that can be updated over time.

        Profile structure includes:
        - name: Speaker's name
        - color: Visual identifier for the speaker
        - history: List of previous sessions/meetings
        - fingerprint: Behavioral fingerprint data
        - statistics: Speaking pattern statistics
        - preferences: Analysis preferences and settings

        The profile system enables advanced features like:
        - Cross-session speaker recognition
        - Behavioral pattern analysis
        - Personalized analysis recommendations
        - Long-term trend tracking
    """
    path = SPEAKER_DIR / f"{name}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    else:
        # Create new profile with default structure
        # Initialize with empty data structures that will be populated over time
        profile = {
            "name": name,
            "color": None,  # Visual identifier for the speaker
            "history": [],  # List of previous sessions/meetings
            "fingerprint": {},  # Behavioral fingerprint data
        }
        with open(path, "w") as f:
            json.dump(profile, f, indent=2)
        return profile


def update_speaker_profile(name: str, data: dict[str, Any]) -> None:
    """
    Save updated speaker profile back to disk.

    This function persists changes to a speaker's profile,
    ensuring that behavioral data and preferences are maintained
    across sessions.

    Args:
        name: Name of the speaker whose profile to update
        data: Updated profile data to save

    Note:
        The profile is saved as a JSON file in the speaker directory
        with the speaker's name as the filename. This allows for:
        - Easy backup and version control
        - Sharing profiles between systems
        - Manual inspection and editing
        - Data portability across installations

        The function automatically creates the speaker directory
        if it doesn't exist, ensuring that profiles can always be saved.
    """
    path = SPEAKER_DIR / f"{name}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


class SpeakerRegistry:
    """
    Central registry for managing speaker profiles and data.

    This class provides a unified interface for accessing and updating
    speaker profiles, with built-in caching for performance. It manages
    speaker colors, fingerprints, and historical data across multiple
    analysis sessions.

    The registry supports:
    - Profile loading and saving with caching
    - Speaker color assignment for visual identification
    - Behavioral fingerprinting and updates
    - Cross-session data persistence
    - Performance optimization through caching

    The registry is designed to be a singleton-like service that
    can be used throughout the TranscriptX system to maintain
    consistent speaker data and improve performance through caching.
    """

    def __init__(self, speaker_dir: Path | None = None):
        """
        Initialize the speaker registry.

        Args:
            speaker_dir: Custom directory for speaker profiles (optional)
                        If not provided, uses the default SPEAKER_DIR

        Note:
            The registry initializes with an empty cache that will be
            populated as profiles are accessed. This provides performance
            benefits when the same speaker profiles are accessed multiple
            times during an analysis session.
        """
        self.speaker_dir = Path(speaker_dir) if speaker_dir else SPEAKER_DIR
        self.speaker_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict[str, Any]] = (
            {}
        )  # In-memory cache for loaded profiles

    def list_speakers(self) -> list[str]:
        """
        Get a list of all speakers with profiles in the registry.

        Returns:
            List of speaker names (without file extensions)

        Note:
            This function scans the speaker directory for JSON files
            and returns the base names as speaker names. It's useful
            for:
            - Discovering available speakers
            - Building speaker selection interfaces
            - Cross-session speaker management
            - Profile maintenance and cleanup
        """
        return [p.stem for p in self.speaker_dir.glob("*.json")]

    def load_profile(self, name: str) -> dict[str, Any]:
        """
        Load a speaker profile, using cache if available.

        Args:
            name: Name of the speaker to load

        Returns:
            Speaker profile dictionary

        Note:
            Profiles are cached in memory after first load for
            improved performance across multiple accesses. The cache
            is maintained for the lifetime of the registry instance.

            If a profile doesn't exist, one will be created automatically
            with default values. This ensures that all speakers have
            profiles that can be updated over time.
        """
        if name in self._cache:
            return self._cache[name]
        profile = get_speaker_profile(name)
        self._cache[name] = profile
        return profile

    def save_profile(self, name: str, profile: dict[str, Any]) -> None:
        """
        Save a speaker profile and update the cache.

        Args:
            name: Name of the speaker
            profile: Profile data to save

        Note:
            This function both saves the profile to disk and updates
            the in-memory cache. This ensures that subsequent accesses
            to the same profile will use the updated data without
            requiring a disk read.
        """
        update_speaker_profile(name, profile)
        self._cache[name] = profile

    def get_speaker_color(self, name: str) -> str | None:
        """
        Get the assigned color for a speaker.

        Args:
            name: Name of the speaker

        Returns:
            Color string (e.g., "#FF0000") or None if not assigned

        Note:
            Speaker colors are used for visual identification in
            charts, graphs, and other visualizations. They help
            users quickly identify different speakers across
            multiple visualizations and analysis outputs.
        """
        profile = self.load_profile(name)
        return profile.get("color")

    def set_speaker_color(self, name: str, color: str) -> None:
        """
        Assign a color to a speaker for visual identification.

        Args:
            name: Name of the speaker
            color: Color string (e.g., "#FF0000")

        Note:
            The color is stored in the speaker's profile and will
            be used consistently across all visualizations and
            analysis outputs. This ensures that users can easily
            identify the same speaker across different charts
            and reports.
        """
        profile = self.load_profile(name)
        profile["color"] = color
        self.save_profile(name, profile)

    def get_speaker_fingerprint(self, name: str) -> dict[str, Any]:
        """
        Get the behavioral fingerprint for a speaker.

        Args:
            name: Name of the speaker

        Returns:
            Dictionary containing behavioral fingerprint data

        Note:
            The behavioral fingerprint contains various metrics
            that characterize the speaker's communication style:
            - Vocabulary patterns (TF-IDF analysis)
            - Speaking rate and segment characteristics
            - Sentiment and emotion patterns
            - Verbal tics and speech patterns
            - Named entity usage patterns
            - Part-of-speech distribution

            This data can be used for:
            - Speaker identification across sessions
            - Behavioral pattern analysis
            - Personalized analysis recommendations
            - Cross-speaker comparison and clustering
        """
        profile = self.load_profile(name)
        return profile.get("fingerprint", {})

    def update_fingerprint_with_stats(
        self, name: str, segments: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Update the speaker's fingerprint with new stats from segments.

        This method performs comprehensive analysis of a speaker's
        segments to build or update their behavioral fingerprint.
        The fingerprint includes multiple linguistic and behavioral
        characteristics that help identify the speaker's patterns.

        Args:
            name: Name of the speaker
            segments: List of transcript segments with analysis data
                     Each segment should have keys like 'text', 'sentiment',
                     'emotion', 'start', 'end', etc.

        Returns:
            Updated fingerprint dictionary

        Note:
            The fingerprint includes:
            - Top terms (TF-IDF analysis)
            - Verbal tics frequency
            - Part-of-speech distribution
            - Average sentiment scores
            - Average emotion scores
            - Speaking rate and segment length
            - Top named entities
        """
        # Extract text from segments
        texts = [seg.get("text", "") for seg in segments if seg.get("text")]
        all_text = " ".join(texts)

        # Analyze vocabulary using TF-IDF
        tfidf = TfidfVectorizer(
            stop_words=ALL_STOPWORDS, ngram_range=(1, 2), max_features=30
        )
        if texts:
            tfidf_matrix = tfidf.fit_transform(texts)
            feature_names = tfidf.get_feature_names_out()
            scores = np.asarray(tfidf_matrix.mean(axis=0)).flatten()
            top_indices = scores.argsort()[::-1][:10]
            top_terms = [feature_names[i] for i in top_indices]
        else:
            top_terms = []

        # Extract and count verbal tics
        tics = extract_tics_from_text(all_text)
        tic_counts = dict(Counter(tics).most_common(10))

        # Analyze part-of-speech distribution
        pos_counts = Counter()
        if texts:
            doc = nlp(all_text)
            for token in doc:
                pos_counts[token.pos_] += 1
            total_pos = sum(pos_counts.values())
            pos_dist = (
                {k: v / total_pos for k, v in pos_counts.items()} if total_pos else {}
            )
        else:
            pos_dist = {}

        # Calculate average sentiment scores
        sentiments = [
            seg.get("sentiment") or score_sentiment(seg.get("text", ""))
            for seg in segments
        ]
        avg_sentiment = {}
        if sentiments:
            for k in ["compound", "pos", "neu", "neg"]:
                avg_sentiment[k] = float(
                    np.mean([s.get(k, 0) for s in sentiments if s])
                )

        # Calculate average emotion scores
        emotions = [
            seg.get("nrc_emotion") or compute_nrc_emotions(seg.get("text", ""))
            for seg in segments
        ]
        avg_emotion = {}
        if emotions:
            all_keys = set().union(*(e.keys() for e in emotions if e))
            for k in all_keys:
                avg_emotion[k] = float(np.mean([e.get(k, 0) for e in emotions if e]))

        # Analyze speaking patterns
        segment_lengths = [
            seg.get("end", 0) - seg.get("start", 0)
            for seg in segments
            if seg.get("end") and seg.get("start")
        ]
        avg_segment_length = float(np.mean(segment_lengths)) if segment_lengths else 0
        word_counts = [
            len(seg.get("text", "").split()) for seg in segments if seg.get("text")
        ]
        speaking_rate = (
            float(
                np.mean(
                    [
                        w / l if l else 0
                        for w, l in zip(word_counts, segment_lengths, strict=False)
                        if l > 0
                    ]
                )
            )
            if segment_lengths
            else 0
        )

        # Extract and count named entities
        entities = []
        for seg in segments:
            entities.extend(
                [ent for ent, label in extract_named_entities(seg.get("text", ""))]
            )
        entity_counts = dict(Counter(entities).most_common(10))

        # Build comprehensive fingerprint
        fingerprint = {
            "top_terms": top_terms,
            "verbal_tics": tic_counts,
            "pos_distribution": pos_dist,
            "avg_sentiment": avg_sentiment,
            "avg_emotion": avg_emotion,
            "avg_segment_length": avg_segment_length,
            "speaking_rate": speaking_rate,
            "top_entities": entity_counts,
        }

        # Save updated profile
        profile = self.load_profile(name)
        profile["fingerprint"] = fingerprint
        self.save_profile(name, profile)
        return fingerprint
