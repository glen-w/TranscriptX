"""
Module requirements and enhancements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple

from .canonical_transcript import TranscriptCapabilities


class Requirement(str, Enum):
    SEGMENTS = "segments"
    SEGMENT_TIMESTAMPS = "segment_timestamps"
    SPEAKER_LABELS = "speaker_labels"
    WORD_TIMESTAMPS = "word_timestamps"
    WORD_SPEAKERS = "word_speakers"
    DATABASE = "database"


class Enhancement(str, Enum):
    SPEAKER_DISPLAY_NAMES = "speaker_display_names"


@dataclass
class ModuleRequirements:
    required: List[Requirement] = field(default_factory=list)
    enhancements: List[Enhancement] = field(default_factory=list)


def check_requirements_met(
    requirements: List[Requirement],
    capabilities: TranscriptCapabilities,
    has_db: bool,
) -> Tuple[bool, List[str]]:
    missing: List[str] = []
    for requirement in requirements:
        if requirement == Requirement.SEGMENTS and not capabilities.has_segments:
            missing.append("Requires segments but transcript has none")
        elif (
            requirement == Requirement.SEGMENT_TIMESTAMPS
            and not capabilities.has_segment_timestamps
        ):
            missing.append(
                "Requires segment timestamps but transcript lacks start/end times"
            )
        elif (
            requirement == Requirement.SPEAKER_LABELS
            and not capabilities.has_speaker_labels
        ):
            missing.append(
                "Requires speaker labels but transcript lacks speaker fields"
            )
        elif (
            requirement == Requirement.WORD_TIMESTAMPS
            and not capabilities.has_word_timestamps
        ):
            missing.append(
                "Requires word-level timestamps but transcript lacks words with start/end"
            )
        elif (
            requirement == Requirement.WORD_SPEAKERS
            and not capabilities.has_word_speakers
        ):
            missing.append(
                "Requires word-level speakers but transcript lacks speaker per word"
            )
        elif requirement == Requirement.DATABASE and not has_db:
            missing.append("Requires database but --persist not set")
    return (len(missing) == 0, missing)
