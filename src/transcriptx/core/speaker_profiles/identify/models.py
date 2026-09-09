"""Typed models for batch speaker auto-identification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ChannelId = Literal["voice", "mention", "style"]
IdentifyAction = Literal["apply", "skip"]
SkipReason = Literal[
    "already_named",
    "ignored",
    "already_linked",
    "abstain",
    "conflict",
    "collision",
    "not_managed",
    "no_profile",
    "human_override",
]


@dataclass(frozen=True)
class ChannelCandidate:
    """One channel's proposal for a diarized ID."""

    channel: ChannelId
    display_name: str
    profile_id: str | None = None
    score: float | None = None
    confidence: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    suggestion_id: str | None = None
    suggestion_digest: str | None = None
    model_generation_id: str | None = None


@dataclass(frozen=True)
class FusedDecision:
    """Fusion outcome for one diarized ID (apply or skip)."""

    local_speaker_key: str
    action: IdentifyAction
    skip_reason: str | None = None
    display_name: str | None = None
    profile_id: str | None = None
    channels: tuple[str, ...] = ()
    confidence: str | None = None
    suggestion_id: str | None = None
    suggestion_digest: str | None = None
    model_generation_id: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpeakerApplyResult:
    """What was written for one diarized ID."""

    local_speaker_key: str
    named: bool = False
    linked: bool = False
    skipped_name_reason: str | None = None
    skipped_link_reason: str | None = None
    display_name: str | None = None
    profile_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class IdentifyResult:
    """Per-transcript identify run."""

    transcript_path: str
    managed_transcript_id: str | None
    auto_name: bool
    auto_link: bool
    dry_run: bool
    decisions: tuple[FusedDecision, ...]
    applied: tuple[SpeakerApplyResult, ...]
    named_count: int = 0
    linked_count: int = 0
    skipped_count: int = 0
    error: str | None = None
    artefact_path: str | None = None
