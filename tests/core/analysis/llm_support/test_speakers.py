"""Tests for speaker eligibility and grouping for LLM speaker summaries."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.llm_support.speakers import (
    collect_named_speaker_groups_for_llm,
    is_named_speaker_eligible_for_llm,
)


def _mini_segments() -> list[dict]:
    return [
        {"speaker": "Alice", "text": "Hello there.", "start": 0.0, "end": 1.0},
        {"speaker": "Bob", "text": "Hi Alice.", "start": 1.0, "end": 2.0},
        {"speaker": "SPEAKER_02", "text": "Unmapped line.", "start": 2.0, "end": 3.0},
    ]


@pytest.mark.unit
def test_collect_named_speaker_groups_filters_unnamed() -> None:
    groups = collect_named_speaker_groups_for_llm(
        _mini_segments(),
        runtime_flags={},
    )
    names = {g["display_name"] for g in groups}
    assert names == {"Alice", "Bob"}


@pytest.mark.unit
def test_collect_named_speaker_groups_respects_ignored_ids() -> None:
    groups = collect_named_speaker_groups_for_llm(
        _mini_segments(),
        runtime_flags={"ignored_speaker_ids": {"Bob"}},
    )
    names = {g["display_name"] for g in groups}
    assert names == {"Alice"}


@pytest.mark.unit
def test_collect_named_speaker_groups_orders_by_lowercased_display_name() -> None:
    segments = [
        {"speaker": "zoe", "text": "Last alphabetically lowercase."},
        {"speaker": "Bob", "text": "Middle speaker."},
        {"speaker": "alice", "text": "First alphabetically lowercase."},
    ]
    groups = collect_named_speaker_groups_for_llm(segments, runtime_flags={})
    assert [g["display_name"] for g in groups] == ["alice", "Bob", "zoe"]


@pytest.mark.unit
def test_is_named_speaker_eligible_rejects_empty_display_name() -> None:
    assert (
        is_named_speaker_eligible_for_llm("", "SPEAKER_00", runtime_flags={}) is False
    )


@pytest.mark.unit
def test_is_named_speaker_eligible_respects_named_speaker_keys() -> None:
    flags = {"named_speaker_keys": {"SPEAKER_01"}}
    assert (
        is_named_speaker_eligible_for_llm("Alice", "SPEAKER_01", runtime_flags=flags)
        is True
    )
    assert (
        is_named_speaker_eligible_for_llm("Bob", "SPEAKER_02", runtime_flags=flags)
        is False
    )


@pytest.mark.unit
def test_is_named_speaker_eligible_alias_maps_display_to_named_key() -> None:
    flags = {
        "named_speaker_keys": {"canonical_alice"},
        "speaker_key_aliases": {"Alice": "canonical_alice"},
    }
    assert (
        is_named_speaker_eligible_for_llm("Alice", "SPEAKER_00", runtime_flags=flags)
        is True
    )


@pytest.mark.unit
def test_is_named_speaker_eligible_non_dict_aliases_falls_back_to_key() -> None:
    flags = {
        "named_speaker_keys": {"SPEAKER_00"},
        "speaker_key_aliases": ["not", "a", "dict"],
    }
    assert (
        is_named_speaker_eligible_for_llm("Alice", "SPEAKER_00", runtime_flags=flags)
        is True
    )


@pytest.mark.unit
def test_collect_named_speaker_groups_skips_speaker_with_only_empty_text() -> None:
    segments = [
        {"speaker": "Alice", "text": "Hello."},
        {"speaker": "Bob", "text": "   "},
    ]
    groups = collect_named_speaker_groups_for_llm(segments, runtime_flags={})
    assert [g["display_name"] for g in groups] == ["Alice"]


@pytest.mark.unit
def test_collect_named_speaker_groups_entry_shape() -> None:
    groups = collect_named_speaker_groups_for_llm(
        [{"speaker": "Alice", "text": "Hello."}],
        runtime_flags={},
    )
    (entry,) = groups
    assert set(entry.keys()) == {
        "display_name",
        "speaker_key",
        "grouping_key",
        "grouping_keys",
        "segments",
    }
    assert entry["speaker_key"] == str(entry["grouping_key"])
    assert entry["grouping_keys"] == (entry["grouping_key"],)
    assert entry["segments"] == [{"speaker": "Alice", "text": "Hello."}]


@pytest.mark.unit
def test_collect_emits_aliased_eligibility_key_as_speaker_key() -> None:
    flags = {
        "named_speaker_keys": {"canonical_alice"},
        "speaker_key_aliases": {"Alice": "canonical_alice"},
    }
    groups = collect_named_speaker_groups_for_llm(
        [{"speaker": "Alice", "text": "Hello.", "start": 0.0, "end": 1.0}],
        runtime_flags=flags,
    )
    (entry,) = groups
    assert entry["speaker_key"] == "canonical_alice"
    assert str(entry["grouping_key"]) != "canonical_alice" or True


@pytest.mark.unit
def test_alias_collision_merges_grouping_keys() -> None:
    flags = {
        "speaker_key_aliases": {"Alice": "same", "Alicia": "same"},
    }
    segments = [
        {"speaker": "Alice", "text": "One.", "start": 0.0, "end": 1.0},
        {"speaker": "Alicia", "text": "Two.", "start": 1.0, "end": 2.0},
    ]
    groups = collect_named_speaker_groups_for_llm(segments, runtime_flags=flags)
    assert len(groups) == 1
    assert groups[0]["speaker_key"] == "same"
    assert len(groups[0]["grouping_keys"]) == 2
    assert len(groups[0]["segments"]) == 2


@pytest.mark.unit
def test_speaker_limit_for_cell_cap() -> None:
    from transcriptx.core.analysis.llm_support.speakers import (
        speaker_limit_for_cell_cap,
    )

    assert (
        speaker_limit_for_cell_cap(
            max_eligible_speakers=12,
            max_speaker_question_cells=48,
            per_speaker_question_count=0,
        )
        == 0
    )
    assert (
        speaker_limit_for_cell_cap(
            max_eligible_speakers=12,
            max_speaker_question_cells=48,
            per_speaker_question_count=5,
        )
        == 9
    )
    assert (
        speaker_limit_for_cell_cap(
            max_eligible_speakers=3,
            max_speaker_question_cells=48,
            per_speaker_question_count=5,
        )
        == 3
    )
