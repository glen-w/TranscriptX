"""Interaction event data structures."""

from dataclasses import dataclass


@dataclass
class InteractionEvent:
    """
    Represents a single speaker interaction event.

    This dataclass captures all relevant information about a speaker interaction,
    including timing, participants, and interaction characteristics.
    """

    timestamp: float  # When the interaction occurred
    speaker_a: str  # First speaker in the interaction
    speaker_b: str  # Second speaker in the interaction
    interaction_type: str  # Type: 'interruption_overlap', 'interruption_gap', 'response'
    speaker_a_text: str  # Text from speaker A
    speaker_b_text: str  # Text from speaker B
    gap_before: float  # Gap before interaction (seconds)
    overlap: float  # Overlap duration (seconds)
    speaker_a_start: float  # Start time of speaker A's segment
    speaker_a_end: float  # End time of speaker A's segment
    speaker_b_start: float  # Start time of speaker B's segment
    speaker_b_end: float  # End time of speaker B's segment
