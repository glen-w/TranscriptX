"""SpeakerRunOptions defaults and immutability (pipeline run contract)."""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from transcriptx.core.pipeline.run_options import SpeakerRunOptions


@pytest.mark.unit
def test_speaker_run_options_defaults_are_conservative() -> None:
    opts = SpeakerRunOptions()
    assert opts.include_unidentified is False
    assert opts.anonymise is False
    assert opts.skip_identification is False
    assert opts.allow_unnamed_speakers is False
    assert opts.treat_as_single_speaker is False


@pytest.mark.unit
def test_speaker_run_options_are_frozen() -> None:
    opts = SpeakerRunOptions(allow_unnamed_speakers=True)
    with pytest.raises(FrozenInstanceError):
        opts.allow_unnamed_speakers = False  # type: ignore[misc]
    assert opts.allow_unnamed_speakers is True


@pytest.mark.unit
def test_speaker_run_options_explicit_flags_preserved() -> None:
    opts = SpeakerRunOptions(
        include_unidentified=True,
        anonymise=True,
        skip_identification=True,
        allow_unnamed_speakers=True,
        treat_as_single_speaker=True,
    )
    assert opts == SpeakerRunOptions(
        include_unidentified=True,
        anonymise=True,
        skip_identification=True,
        allow_unnamed_speakers=True,
        treat_as_single_speaker=True,
    )
