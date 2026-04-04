from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpeakerRunOptions:
    include_unidentified: bool = False
    anonymise: bool = False
    skip_identification: bool = False
