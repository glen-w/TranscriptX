"""Assistive speaker name suggestions (user-confirmed; never auto-writes)."""

from transcriptx.core.speaker_profiles.identify.suggestions.service import (
    SPEAKER_NAME_SUGGESTIONS_CONSUMER_ID,
    suggest_speaker_names,
)

__all__ = ["SPEAKER_NAME_SUGGESTIONS_CONSUMER_ID", "suggest_speaker_names"]
