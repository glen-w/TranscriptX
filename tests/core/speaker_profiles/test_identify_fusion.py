"""Fusion table for speaker auto-identification."""

from __future__ import annotations

import pytest

from transcriptx.core.speaker_profiles.identify.fusion import fuse_speaker_candidates
from transcriptx.core.speaker_profiles.identify.models import ChannelCandidate


def _voice(name: str, profile: str, *, confidence: str = "strong") -> ChannelCandidate:
    return ChannelCandidate(
        channel="voice",
        display_name=name,
        profile_id=profile,
        confidence=confidence,
        score=0.9,
    )


def _mention(name: str, profile: str | None = None) -> ChannelCandidate:
    return ChannelCandidate(
        channel="mention",
        display_name=name,
        profile_id=profile,
        confidence="possible",
        score=1.0,
    )


def _style(name: str, profile: str) -> ChannelCandidate:
    return ChannelCandidate(
        channel="style",
        display_name=name,
        profile_id=profile,
        confidence="strong",
        score=0.92,
    )


@pytest.mark.unit
def test_strong_voice_applies_when_mention_silent() -> None:
    decisions = fuse_speaker_candidates(
        speaker_ids=["SPEAKER_00"],
        voice={"SPEAKER_00": _voice("Maya", "p-maya")},
        mentions={},
        style={},
    )
    assert decisions[0].action == "apply"
    assert decisions[0].display_name == "Maya"
    assert decisions[0].profile_id == "p-maya"


@pytest.mark.unit
def test_strong_voice_conflicts_with_mention() -> None:
    decisions = fuse_speaker_candidates(
        speaker_ids=["SPEAKER_00"],
        voice={"SPEAKER_00": _voice("Maya", "p-maya")},
        mentions={"SPEAKER_00": _mention("Jordan")},
        style={},
    )
    assert decisions[0].action == "skip"
    assert decisions[0].skip_reason == "conflict"


@pytest.mark.unit
def test_mention_only_applies_name() -> None:
    decisions = fuse_speaker_candidates(
        speaker_ids=["SPEAKER_00"],
        voice={},
        mentions={"SPEAKER_00": _mention("Sam")},
        style={},
    )
    assert decisions[0].action == "apply"
    assert decisions[0].display_name == "Sam"
    assert decisions[0].profile_id is None


@pytest.mark.unit
def test_mention_matching_profile_can_link() -> None:
    decisions = fuse_speaker_candidates(
        speaker_ids=["SPEAKER_00"],
        voice={},
        mentions={"SPEAKER_00": _mention("Maya", "p-maya")},
        style={},
    )
    assert decisions[0].action == "apply"
    assert decisions[0].profile_id == "p-maya"


@pytest.mark.unit
def test_style_only_skipped_unless_enabled() -> None:
    decisions = fuse_speaker_candidates(
        speaker_ids=["SPEAKER_00"],
        voice={},
        mentions={},
        style={"SPEAKER_00": _style("Maya", "p-maya")},
        style_only_apply=False,
    )
    assert decisions[0].action == "skip"
    assert decisions[0].skip_reason == "abstain"

    enabled = fuse_speaker_candidates(
        speaker_ids=["SPEAKER_00"],
        voice={},
        mentions={},
        style={"SPEAKER_00": _style("Maya", "p-maya")},
        style_only_apply=True,
    )
    assert enabled[0].action == "apply"
    assert enabled[0].profile_id == "p-maya"


@pytest.mark.unit
def test_collision_two_speakers_same_profile() -> None:
    decisions = fuse_speaker_candidates(
        speaker_ids=["SPEAKER_00", "SPEAKER_01"],
        voice={
            "SPEAKER_00": _voice("Maya", "p-maya"),
            "SPEAKER_01": _voice("Maya", "p-maya"),
        },
        mentions={},
        style={},
    )
    assert all(d.action == "skip" for d in decisions)
    assert all(d.skip_reason == "collision" for d in decisions)


@pytest.mark.unit
def test_collision_same_display_name() -> None:
    decisions = fuse_speaker_candidates(
        speaker_ids=["SPEAKER_00", "SPEAKER_01"],
        voice={},
        mentions={
            "SPEAKER_00": _mention("Sam"),
            "SPEAKER_01": _mention("Sam"),
        },
        style={},
    )
    assert all(d.skip_reason == "collision" for d in decisions)
