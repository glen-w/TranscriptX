"""
Transcript data fixtures for testing.

This module provides various transcript data structures for testing
different scenarios and edge cases.
"""

import json
from pathlib import Path
from typing import Any, Dict, List


def get_minimal_transcript() -> Dict[str, Any]:
    """Get minimal valid transcript data."""
    return {
        "segments": [
            {
                "speaker": "SPEAKER_00",
                "text": "Hello world",
                "start": 0.0,
                "end": 1.0
            }
        ]
    }


def get_multi_speaker_transcript() -> Dict[str, Any]:
    """Get transcript with multiple speakers."""
    return {
        "segments": [
            {
                "speaker": "SPEAKER_00",
                "text": "Welcome to our meeting.",
                "start": 0.0,
                "end": 2.5
            },
            {
                "speaker": "SPEAKER_01",
                "text": "Thank you for having me.",
                "start": 3.0,
                "end": 5.0
            },
            {
                "speaker": "SPEAKER_00",
                "text": "Let's discuss the project.",
                "start": 5.5,
                "end": 7.0
            }
        ]
    }


def get_long_transcript() -> Dict[str, Any]:
    """Get longer transcript for performance testing."""
    segments = []
    speakers = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
    texts = [
        "This is a longer conversation for testing purposes.",
        "We need to ensure our analysis can handle extended transcripts.",
        "The system should be able to process many segments efficiently.",
        "Performance testing is important for production use.",
        "Let's make sure everything works correctly."
    ]
    
    for i in range(50):  # 50 segments
        segments.append({
            "speaker": speakers[i % len(speakers)],
            "text": texts[i % len(texts)] + f" (Segment {i+1})",
            "start": float(i * 2),
            "end": float(i * 2 + 1.5)
        })
    
    return {"segments": segments}


def get_transcript_with_emotions() -> Dict[str, Any]:
    """Get transcript with emotional content for emotion analysis testing."""
    return {
        "segments": [
            {
                "speaker": "SPEAKER_00",
                "text": "I'm so excited about this project!",
                "start": 0.0,
                "end": 3.0
            },
            {
                "speaker": "SPEAKER_01",
                "text": "I'm worried about the timeline though.",
                "start": 3.5,
                "end": 6.0
            },
            {
                "speaker": "SPEAKER_00",
                "text": "Don't worry, we'll figure it out together!",
                "start": 6.5,
                "end": 9.0
            }
        ]
    }


def get_transcript_with_entities() -> Dict[str, Any]:
    """Get transcript with named entities for NER testing."""
    return {
        "segments": [
            {
                "speaker": "SPEAKER_00",
                "text": "I'm flying to New York tomorrow for the conference.",
                "start": 0.0,
                "end": 4.0
            },
            {
                "speaker": "SPEAKER_01",
                "text": "That sounds great! I'll be in San Francisco next week.",
                "start": 4.5,
                "end": 8.0
            },
            {
                "speaker": "SPEAKER_00",
                "text": "Maybe we can meet at the Google office in Mountain View.",
                "start": 8.5,
                "end": 12.0
            }
        ]
    }


def get_invalid_transcript_missing_segments() -> Dict[str, Any]:
    """Get invalid transcript missing segments key."""
    return {
        "metadata": {
            "duration": 120.0,
            "language": "en"
        }
    }


def get_invalid_transcript_empty_segments() -> Dict[str, Any]:
    """Get invalid transcript with empty segments."""
    return {
        "segments": []
    }


def get_sample_speaker_map() -> Dict[str, str]:
    """
    Get sample speaker mapping for testing (DEPRECATED).
    
    Returns empty dict. Use segments with speaker_db_id instead.
    """
    import warnings
    warnings.warn(
        "get_sample_speaker_map() is deprecated. Use segments with speaker_db_id instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return {}  # Return empty dict for backward compatibility


def create_test_transcript_file(file_path: Path, transcript_data: Dict[str, Any]) -> None:
    """Create a test transcript file with the given data."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(transcript_data, indent=2))
