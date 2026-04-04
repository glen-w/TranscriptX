"""
Unit tests for group-level speaker normalization (core pipeline).
"""

from __future__ import annotations

from unittest.mock import patch


from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import (
    CanonicalSpeakerMap,
    normalize_speakers_across_transcripts,
)


def _make_result(transcript_path: str, transcript_key: str) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=transcript_path,
        transcript_key=transcript_key,
        run_id="run-1",
        order_index=0,
        output_dir="/out",
        module_results={},
    )


class TestNormalizeSpeakersAcrossTranscripts:
    """Tests for normalize_speakers_across_transcripts (fallback path, no DB)."""

    def test_returns_canonical_speaker_map(self):
        """normalize_speakers_across_transcripts returns CanonicalSpeakerMap."""
        with patch(
            "transcriptx.core.pipeline.speaker_normalizer.TranscriptService"
        ) as mock_ts:
            mock_ts.return_value.load_segments.return_value = [
                {"speaker": "Alice", "text": "Hi", "start": 0.0, "end": 1.0},
                {"speaker": "Bob", "text": "Hello", "start": 1.0, "end": 2.0},
            ]
            results = [
                _make_result("/path/to/t1.json", "key1"),
            ]
            out = normalize_speakers_across_transcripts(results)
        assert isinstance(out, CanonicalSpeakerMap)
        assert out.transcript_to_speakers is not None
        assert out.canonical_to_display is not None
        assert out.transcript_to_display is not None

    def test_fallback_canonical_id_is_stable(self):
        """normalize_speakers_across_transcripts uses deterministic fallback IDs."""
        with patch(
            "transcriptx.core.pipeline.speaker_normalizer.TranscriptService"
        ) as mock_ts:
            mock_ts.return_value.load_segments.return_value = [
                {"speaker": "Alice", "text": "Hi", "start": 0.0, "end": 1.0},
            ]
            results = [_make_result("/t.json", "k1")]
            out = normalize_speakers_across_transcripts(results)
        assert "/t.json" in out.transcript_to_speakers
        local_to_canonical = out.transcript_to_speakers["/t.json"]
        assert "Alice" in local_to_canonical
        assert isinstance(local_to_canonical["Alice"], int)
        assert "/t.json" in out.transcript_to_display
