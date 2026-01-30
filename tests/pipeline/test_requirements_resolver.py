"""Tests for module requirements resolver."""

from __future__ import annotations

from transcriptx.core.domain.canonical_transcript import TranscriptCapabilities
from transcriptx.core.domain.module_requirements import Requirement
from transcriptx.core.pipeline.requirements_resolver import ModuleRequirementsResolver


def test_should_skip_missing_segments() -> None:
    capabilities = TranscriptCapabilities(
        has_segments=False,
        has_segment_timestamps=False,
        has_speaker_labels=False,
        has_word_timestamps=False,
        has_word_speakers=False,
    )
    resolver = ModuleRequirementsResolver(capabilities=capabilities, has_db=False)
    should_skip, reasons = resolver.should_skip([Requirement.SEGMENTS])
    assert should_skip is True
    assert any("Requires segments" in reason for reason in reasons)


def test_should_not_skip_when_requirements_met() -> None:
    capabilities = TranscriptCapabilities(
        has_segments=True,
        has_segment_timestamps=True,
        has_speaker_labels=True,
        has_word_timestamps=False,
        has_word_speakers=False,
    )
    resolver = ModuleRequirementsResolver(capabilities=capabilities, has_db=True)
    should_skip, reasons = resolver.should_skip(
        [Requirement.SEGMENTS, Requirement.SEGMENT_TIMESTAMPS, Requirement.SPEAKER_LABELS]
    )
    assert should_skip is False
    assert reasons == []
