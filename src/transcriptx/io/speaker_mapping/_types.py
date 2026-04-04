"""Shared type definitions for speaker mapping."""

from __future__ import annotations

from typing import Literal, NamedTuple, Optional, Union

GO_BACK_SENTINEL = "__GO_BACK__"
EXIT_SENTINEL = "__EXIT__"

ActionType = Literal["name", "ignore", "skip"]


class SpeakerChoice(NamedTuple):
    action: ActionType
    value: Optional[str] = None


SpeakerSelection = Union[SpeakerChoice, str]
