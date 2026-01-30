"""
Tests for VTT parser and importer.

This module tests the WebVTT parsing functionality, speaker normalization,
segment coalescing, and end-to-end import workflow.
"""

import json
import tempfile
from pathlib import Path

import pytest

from transcriptx.io.segment_coalescer import CoalesceConfig, coalesce_segments
from transcriptx.io.speaker_normalizer import normalize_speakers
from transcriptx.io.transcript_importer import import_transcript, ensure_json_artifact
from transcriptx.io.vtt_parser import parse_vtt_file, parse_vtt_timestamp, VTTCue


# Test fixtures path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "vtt"
SRT_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "srt"


class TestVTTParser:
    """Tests for VTT parser."""
    
    def test_parse_simple_vtt(self):
        """Test parsing a simple VTT file."""
        vtt_path = FIXTURES_DIR / "simple.vtt"
        cues = parse_vtt_file(vtt_path)
        
        assert len(cues) == 3
        assert cues[0].start == 0.0
        assert cues[0].end == 5.5
        assert cues[0].text == "First subtitle text"
        assert cues[1].text == "Second subtitle text"
        assert cues[2].text == "Third subtitle with multiple words"
    
    def test_parse_vtt_with_speakers(self):
        """Test parsing VTT with speaker hints."""
        vtt_path = FIXTURES_DIR / "with_speakers.vtt"
        cues = parse_vtt_file(vtt_path)
        
        assert len(cues) == 3
        assert cues[0].speaker_hint == "Alice"
        assert cues[0].text == "Hello, how are you?"
        assert cues[1].speaker_hint == "Bob"
        assert cues[2].speaker_hint == "Alice"
    
    def test_parse_vtt_with_cue_ids(self):
        """Test parsing VTT with cue IDs."""
        vtt_path = FIXTURES_DIR / "with_cue_ids.vtt"
        cues = parse_vtt_file(vtt_path)
        
        assert len(cues) == 2
        assert cues[0].id == "cue-1"
        assert cues[1].id == "cue-2"
    
    def test_parse_vtt_with_settings(self):
        """Test parsing VTT with cue settings."""
        vtt_path = FIXTURES_DIR / "with_settings.vtt"
        cues = parse_vtt_file(vtt_path)
        
        assert len(cues) == 2
        assert cues[0].settings is not None
        assert cues[0].settings.get("align") == "start"
        assert cues[0].settings.get("position") == "10%"
    
    def test_parse_vtt_overlapping(self):
        """Test parsing VTT with overlapping cues."""
        vtt_path = FIXTURES_DIR / "overlapping.vtt"
        cues = parse_vtt_file(vtt_path)
        
        assert len(cues) == 3
        # Should preserve order and warn about overlaps
    
    def test_parse_vtt_out_of_order(self):
        """Test parsing VTT with out-of-order cues."""
        vtt_path = FIXTURES_DIR / "out_of_order.vtt"
        cues = parse_vtt_file(vtt_path)
        
        assert len(cues) == 3
        # Should preserve original order
    
    def test_parse_vtt_note_and_style(self):
        """Test parsing VTT with NOTE and STYLE blocks."""
        vtt_path = FIXTURES_DIR / "note_and_style.vtt"
        cues = parse_vtt_file(vtt_path)
        
        assert len(cues) == 1
        assert cues[0].text == "Actual subtitle text"
    
    def test_parse_short_timestamps(self):
        """Test parsing VTT with short timestamp format (MM:SS.mmm)."""
        vtt_path = FIXTURES_DIR / "short_timestamps.vtt"
        cues = parse_vtt_file(vtt_path)
        
        assert len(cues) == 2
        assert cues[0].start == 5.5
        assert cues[0].end == 10.0
    
    def test_parse_vtt_timestamp_standard(self):
        """Test parsing standard timestamp format."""
        assert parse_vtt_timestamp("00:00:05.500") == 5.5
        assert parse_vtt_timestamp("01:02:03.456") == 3723.456
    
    def test_parse_vtt_timestamp_short(self):
        """Test parsing short timestamp format."""
        assert parse_vtt_timestamp("00:05.500") == 5.5
        assert parse_vtt_timestamp("01:23.456") == 83.456


class TestSpeakerNormalizer:
    """Tests for speaker normalization."""
    
    def test_normalize_speakers_with_hints(self):
        """Test normalizing speakers from VTT cues."""
        vtt_path = FIXTURES_DIR / "with_speakers.vtt"
        cues = parse_vtt_file(vtt_path)
        segments = normalize_speakers(cues)
        
        assert len(segments) == 3
        # Check that speakers are normalized
        speakers = [seg.get("speaker") for seg in segments]
        assert "SPEAKER_00" in speakers
        assert "SPEAKER_01" in speakers
        assert None not in speakers
    
    def test_normalize_speakers_without_hints(self):
        """Test normalizing when no speaker hints exist."""
        vtt_path = FIXTURES_DIR / "simple.vtt"
        cues = parse_vtt_file(vtt_path)
        segments = normalize_speakers(cues)
        
        assert len(segments) == 3
        # All speakers should be null
        for seg in segments:
            assert seg.get("speaker") is None


class TestSegmentCoalescer:
    """Tests for segment coalescing."""
    
    def test_coalesce_segments_disabled(self):
        """Test coalescing when disabled."""
        segments = [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00", "text": "First"},
            {"start": 5.5, "end": 10.0, "speaker": "SPEAKER_00", "text": "Second"},
        ]
        config = CoalesceConfig(enabled=False)
        result = coalesce_segments(segments, config)
        
        assert len(result) == 2
        assert result == segments
    
    def test_coalesce_segments_enabled(self):
        """Test coalescing when enabled."""
        segments = [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00", "text": "First"},
            {"start": 5.2, "end": 10.0, "speaker": "SPEAKER_00", "text": "Second"},
        ]
        config = CoalesceConfig(enabled=True, max_gap_ms=500.0)
        result = coalesce_segments(segments, config)
        
        assert len(result) == 1
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 10.0
        assert "First Second" in result[0]["text"]


class TestTranscriptImporter:
    """Tests for transcript importer."""
    
    def test_import_vtt_creates_json(self):
        """Test that importing VTT creates a valid JSON artifact."""
        vtt_path = FIXTURES_DIR / "simple.vtt"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = import_transcript(vtt_path, output_dir=tmpdir)
            
            assert json_path.exists()
            assert json_path.suffix == ".json"
            
            # Load and validate JSON
            with open(json_path, 'r') as f:
                document = json.load(f)
            
            # Check schema
            assert "schema_version" in document
            assert "source" in document
            assert "metadata" in document
            assert "segments" in document
            
            # Check source info
            assert document["source"]["type"] == "vtt"
            assert document["source"]["original_path"] == str(vtt_path.resolve())
            
            # Check segments
            assert len(document["segments"]) == 3
            for seg in document["segments"]:
                assert "start" in seg
                assert "end" in seg
                assert "speaker" in seg
                assert "text" in seg
    
    def test_ensure_json_artifact_vtt(self):
        """Test ensure_json_artifact with VTT file."""
        vtt_path = FIXTURES_DIR / "simple.vtt"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = ensure_json_artifact(vtt_path)
            
            # Should return a JSON path (may be in default location)
            assert json_path.suffix == ".json"
            assert json_path.exists()
    
    def test_ensure_json_artifact_json(self):
        """Test ensure_json_artifact with JSON file."""
        # Create a temporary JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"segments": []}, f)
            json_path = Path(f.name)
        
        try:
            result_path = ensure_json_artifact(json_path)
            assert result_path == json_path
        finally:
            json_path.unlink()
    
    def test_import_vtt_with_speakers(self):
        """Test importing VTT with speaker hints."""
        vtt_path = FIXTURES_DIR / "with_speakers.vtt"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = import_transcript(vtt_path, output_dir=tmpdir)
            
            with open(json_path, 'r') as f:
                document = json.load(f)
            
            # Check that speakers are normalized
            speakers = [seg.get("speaker") for seg in document["segments"]]
            assert None not in speakers
            assert "SPEAKER_00" in speakers
            assert "SPEAKER_01" in speakers

    def test_import_srt_creates_json(self):
        """Test that importing SRT creates a valid JSON artifact."""
        srt_path = SRT_FIXTURES_DIR / "simple.srt"

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = import_transcript(srt_path, output_dir=tmpdir)

            assert json_path.exists()
            assert json_path.suffix == ".json"

            with open(json_path, "r") as f:
                document = json.load(f)

            assert document["source"]["type"] == "srt"
            assert document["source"]["original_path"] == str(srt_path.resolve())
            assert len(document["segments"]) == 3

    def test_ensure_json_artifact_srt(self):
        """Test ensure_json_artifact with SRT file."""
        srt_path = SRT_FIXTURES_DIR / "simple.srt"
        json_path = ensure_json_artifact(srt_path)
        assert json_path.exists()


class TestEndToEnd:
    """End-to-end tests."""
    
    def test_vtt_import_then_analysis(self):
        """Test that VTT import produces JSON that can be used for analysis."""
        vtt_path = FIXTURES_DIR / "simple.vtt"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Import VTT
            json_path = import_transcript(vtt_path, output_dir=tmpdir)
            
            # Verify JSON can be loaded by transcript loader
            from transcriptx.io.transcript_loader import load_segments
            segments = load_segments(str(json_path))
            
            assert len(segments) == 3
            assert all("start" in seg for seg in segments)
            assert all("end" in seg for seg in segments)
            assert all("text" in seg for seg in segments)
