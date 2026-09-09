"""In-transcript name / vocative extractor."""

from __future__ import annotations

import pytest

from transcriptx.core.speaker_profiles.identify.mentions import (
    attach_profile_ids,
    extract_mention_candidates,
    title_person_name,
)


@pytest.mark.unit
def test_title_person_name() -> None:
    assert title_person_name("maya") == "Maya"
    assert title_person_name("MARY JANE") == "Mary Jane"
    assert title_person_name("thanks") == ""


@pytest.mark.unit
def test_self_intro_assigns_to_speaker() -> None:
    segments = [
        {"speaker": "SPEAKER_00", "text": "Hi everyone, I'm Maya."},
        {"speaker": "SPEAKER_01", "text": "Thanks, good to meet you."},
    ]
    winners = extract_mention_candidates(segments)
    assert winners["SPEAKER_00"].display_name == "Maya"


@pytest.mark.unit
def test_two_party_vocative_assigns_to_other() -> None:
    segments = [
        {"speaker": "SPEAKER_00", "text": "Thanks Sam, that helps."},
        {"speaker": "SPEAKER_01", "text": "No problem."},
    ]
    winners = extract_mention_candidates(segments)
    assert winners["SPEAKER_01"].display_name == "Sam"


@pytest.mark.unit
def test_tie_does_not_assign() -> None:
    segments = [
        {"speaker": "SPEAKER_00", "text": "I'm Maya."},
        {"speaker": "SPEAKER_00", "text": "I'm Jordan."},
    ]
    winners = extract_mention_candidates(segments)
    assert "SPEAKER_00" not in winners


@pytest.mark.unit
def test_attach_unique_profile_name() -> None:
    segments = [{"speaker": "SPEAKER_00", "text": "My name is Maya."}]
    winners = extract_mention_candidates(segments)
    attached = attach_profile_ids(
        winners, profiles=[("pid-1", "Maya"), ("pid-2", "Jordan")]
    )
    assert attached["SPEAKER_00"].profile_id == "pid-1"
