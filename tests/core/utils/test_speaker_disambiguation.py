"""
Tests for speaker disambiguation when segments carry stable speaker ids.

This module tests behavior that distinguishes multiple speakers with the same
name using ``speaker_db_id`` (legacy JSON field) when present.
"""

import pytest

from transcriptx.core.utils.speaker_extraction import (
    clear_speaker_display_map,
    extract_speaker_info,
    get_speaker_display_name,
    get_unique_speakers,
    group_segments_by_speaker,
    set_speaker_display_map,
)


class TestSpeakerDisambiguation:
    """Tests for speaker disambiguation with segment-based approach."""

    def test_extract_speaker_info_with_db_id(self):
        """Test extracting speaker info when speaker_db_id is present."""
        segment = {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Hello world",
            "start": 0.0,
            "end": 2.0,
        }

        info = extract_speaker_info(segment)

        assert info is not None
        assert info.grouping_key == 1  # Uses db_id as grouping key
        assert info.display_name == "Alice"
        assert info.db_id == 1

    def test_extract_speaker_info_without_db_id(self):
        """Test extracting speaker info when only speaker name is present."""
        segment = {"speaker": "Alice", "text": "Hello world", "start": 0.0, "end": 2.0}

        info = extract_speaker_info(segment)

        assert info is not None
        assert info.grouping_key == "Alice"  # Uses name as grouping key
        assert info.display_name == "Alice"
        assert info.db_id is None

    def test_disambiguate_same_name_different_db_id(self):
        """Test disambiguation of speakers with same name but different db_ids."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "First Alice speaking",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 2,
                "text": "Second Alice speaking",
                "start": 2.5,
                "end": 4.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 3,
                "text": "Bob speaking",
                "start": 4.5,
                "end": 6.0,
            },
        ]

        # Get unique speakers - should disambiguate the two Alices
        unique_speakers = get_unique_speakers(segments)

        # Should have 3 unique speakers (2 Alices + 1 Bob)
        assert len(unique_speakers) == 3

        # Check that both Alices are present with disambiguation
        db_ids = [1, 2, 3]
        for db_id in db_ids:
            assert db_id in unique_speakers

        # Check display names
        assert unique_speakers[1] == "Alice (ID: 1)" or unique_speakers[1] == "Alice"
        assert unique_speakers[2] == "Alice (ID: 2)" or unique_speakers[2] == "Alice"
        assert unique_speakers[3] == "Bob"

    def test_group_segments_by_speaker_with_db_id(self):
        """Test grouping segments by speaker using db_id."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "First message",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Second message",
                "start": 2.5,
                "end": 4.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Bob's message",
                "start": 4.5,
                "end": 6.0,
            },
        ]

        grouped = group_segments_by_speaker(segments)

        # Should have 2 groups (Alice with db_id=1, Bob with db_id=2)
        assert len(grouped) == 2

        # Check Alice's segments (grouped by db_id=1)
        assert 1 in grouped
        assert len(grouped[1]) == 2
        assert grouped[1][0]["text"] == "First message"
        assert grouped[1][1]["text"] == "Second message"

        # Check Bob's segments (grouped by db_id=2)
        assert 2 in grouped
        assert len(grouped[2]) == 1
        assert grouped[2][0]["text"] == "Bob's message"

    def test_get_speaker_display_name_with_disambiguation(self):
        """Test getting display name with disambiguation when needed."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "First Alice",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 2,
                "text": "Second Alice",
                "start": 2.5,
                "end": 4.0,
            },
        ]

        # Get display name for first Alice
        display_name_1 = get_speaker_display_name(1, [segments[0]], segments)
        display_name_2 = get_speaker_display_name(2, [segments[1]], segments)

        # Both should be disambiguated since there are two Alices
        assert "Alice" in display_name_1
        assert "Alice" in display_name_2
        # At least one should have ID disambiguation
        assert "(ID:" in display_name_1 or "(ID:" in display_name_2

    def test_get_speaker_display_name_no_disambiguation_needed(self):
        """Test getting display name when disambiguation is not needed."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Alice speaking",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Bob speaking",
                "start": 2.5,
                "end": 4.0,
            },
        ]

        # Get display name for Alice (unique name, no disambiguation needed)
        display_name = get_speaker_display_name(1, [segments[0]], segments)

        assert display_name == "Alice"
        assert "(ID:" not in display_name

    def test_handles_missing_speaker_field(self):
        """Test handling of segments without speaker field."""
        segment = {"text": "No speaker", "start": 0.0, "end": 2.0}

        info = extract_speaker_info(segment)

        # Should return None when no speaker info is available
        assert info is None

    def test_handles_unnamed_speaker(self):
        """Test handling of segments with system-generated speaker IDs."""
        segment = {
            "speaker": "SPEAKER_00",
            "speaker_db_id": 1,
            "text": "System speaker",
            "start": 0.0,
            "end": 2.0,
        }

        info = extract_speaker_info(segment)

        assert info is not None
        assert info.grouping_key == 1
        # Display name should use db_id since speaker is not a named speaker
        assert info.display_name in ["SPEAKER_00", "Speaker 1"]

    def test_group_segments_preserves_all_segments(self):
        """Test that grouping preserves all segments."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "A1",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "B1",
                "start": 1.0,
                "end": 2.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "A2",
                "start": 2.0,
                "end": 3.0,
            },
            {
                "speaker": "Charlie",
                "speaker_db_id": 3,
                "text": "C1",
                "start": 3.0,
                "end": 4.0,
            },
        ]

        grouped = group_segments_by_speaker(segments)

        # Count total segments across all groups
        total_grouped = sum(len(segs) for segs in grouped.values())

        assert total_grouped == len(segments)
        assert len(grouped) == 3  # Three unique speakers

    def test_get_unique_speakers_returns_correct_mapping(self):
        """Test that get_unique_speakers returns correct grouping_key -> display_name mapping."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "A1",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 2,
                "text": "A2",
                "start": 1.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 3,
                "text": "B1",
                "start": 2.0,
                "end": 3.0,
            },
        ]

        unique_speakers = get_unique_speakers(segments)

        # Should map grouping_key (db_id) to display_name
        assert 1 in unique_speakers
        assert 2 in unique_speakers
        assert 3 in unique_speakers

        # All should have "Alice" or "Bob" in the name
        assert "Alice" in unique_speakers[1] or "Alice" in unique_speakers[2]
        assert "Bob" in unique_speakers[3]


class TestSpeakerDisplayMapLookup:
    """Sidecar keys are normalized; segment grouping keys may be unpadded or numeric."""

    @pytest.fixture(autouse=True)
    def _clear_display_map(self) -> None:
        clear_speaker_display_map()
        yield
        clear_speaker_display_map()

    def test_display_map_resolves_unpadded_speaker_id(self) -> None:
        """SPEAKER_3 in segments matches sidecar key SPEAKER_03."""
        set_speaker_display_map({"SPEAKER_03": "Alice"})
        segs = [{"speaker": "SPEAKER_3", "text": "x"}]
        assert get_speaker_display_name("SPEAKER_3", segs, segs) == "Alice (SPEAKER_3)"

    def test_display_map_resolves_numeric_string_id(self) -> None:
        """Numeric diarization id string matches normalized SPEAKER_XX sidecar key."""
        set_speaker_display_map({"SPEAKER_03": "Bob"})
        segs = [{"speaker": "3", "text": "x"}]
        assert get_speaker_display_name("3", segs, segs) == "Bob (3)"

    def test_display_map_raw_key_fallback_for_custom_ids(self) -> None:
        """Non-diarization custom keys still resolve by exact match."""
        set_speaker_display_map({"custom-room-a": "Facilitator"})
        segs = [{"speaker": "custom-room-a", "text": "x"}]
        assert (
            get_speaker_display_name("custom-room-a", segs, segs)
            == "Facilitator (custom-room-a)"
        )
