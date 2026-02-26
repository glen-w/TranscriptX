"""
Lightweight fuzz tests for transcript invariants.
"""

import json
import random

import pytest

from transcriptx.core.utils.canonicalization import compute_transcript_content_hash
from transcriptx.core.utils.validation import validate_transcript_file


@pytest.mark.unit
def test_fuzz_transcript_hash_idempotent(tmp_path):
    """Randomized transcripts should hash deterministically."""
    random.seed(42)
    segments = []
    current_time = 0.0
    for i in range(50):
        duration = random.uniform(0.1, 2.0)
        segment = {
            "speaker": f"SPEAKER_{i % 3:02d}",
            "text": f"Segment {i} text",
            "start": current_time,
            "end": current_time + duration,
        }
        segments.append(segment)
        current_time += duration + random.uniform(0.0, 0.3)

    transcript = {"segments": segments}
    transcript_path = tmp_path / "fuzz.json"
    transcript_path.write_text(json.dumps(transcript))

    assert validate_transcript_file(str(transcript_path)) is True

    first = compute_transcript_content_hash(segments)
    second = compute_transcript_content_hash(segments)
    assert first == second


@pytest.mark.unit
def test_fuzz_segment_ordering_invariant(tmp_path):
    """Ensure validation passes for ordered timestamps."""
    random.seed(7)
    segments = []
    current_time = 0.0
    for i in range(30):
        duration = random.uniform(0.1, 1.0)
        segments.append(
            {
                "speaker": "SPEAKER_00",
                "text": f"Line {i}",
                "start": current_time,
                "end": current_time + duration,
            }
        )
        current_time += duration

    transcript_path = tmp_path / "ordered.json"
    transcript_path.write_text(json.dumps({"segments": segments}))
    assert validate_transcript_file(str(transcript_path)) is True
