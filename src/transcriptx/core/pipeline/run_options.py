"""Speaker-related options for a pipeline run."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpeakerRunOptions:
    include_unidentified: bool = False
    anonymise: bool = False
    skip_identification: bool = False
    # Per-run ungate: treat diarized labels (SPEAKER_00, …) as eligible speakers.
    # Combined with analysis.allow_unnamed_speakers (OR). Both default False.
    allow_unnamed_speakers: bool = False
    # T1: monologue opt-in — when exactly one turn-taking speaker, use turn-taking gate.
    treat_as_single_speaker: bool = False
