"""Explicit fusion table for voice + mention + style candidates."""

from __future__ import annotations

from collections import defaultdict

from transcriptx.core.speaker_profiles.identify.mentions import normalize_person_key
from transcriptx.core.speaker_profiles.identify.models import (
    ChannelCandidate,
    FusedDecision,
)
from transcriptx.io.speaker_map_resolver import normalize_diarized_id


def _is_strong(cand: ChannelCandidate | None) -> bool:
    if cand is None:
        return False
    return (cand.confidence or "") == "strong"


def _names_agree(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return True
    return normalize_person_key(left) == normalize_person_key(right)


def _profiles_agree(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return True
    return left == right


def fuse_speaker_candidates(
    *,
    speaker_ids: list[str],
    voice: dict[str, ChannelCandidate],
    mentions: dict[str, ChannelCandidate],
    style: dict[str, ChannelCandidate],
    style_only_apply: bool = False,
) -> list[FusedDecision]:
    """Apply the v1 fusion table; skip on conflict or cross-speaker collision."""
    per_speaker: dict[str, FusedDecision] = {}
    for raw_id in speaker_ids:
        speaker = normalize_diarized_id(raw_id) or raw_id
        v = voice.get(speaker)
        m = mentions.get(speaker)
        s = style.get(speaker)
        per_speaker[speaker] = _fuse_one(
            speaker,
            voice=v,
            mention=m,
            style=s,
            style_only_apply=style_only_apply,
        )

    claimed_profile: dict[str, list[str]] = defaultdict(list)
    claimed_name: dict[str, list[str]] = defaultdict(list)
    for speaker, decision in per_speaker.items():
        if decision.action != "apply":
            continue
        if decision.profile_id:
            claimed_profile[decision.profile_id].append(speaker)
        if decision.display_name:
            claimed_name[normalize_person_key(decision.display_name)].append(speaker)

    collided: set[str] = set()
    for holders in list(claimed_profile.values()) + list(claimed_name.values()):
        if len(set(holders)) > 1:
            collided.update(holders)

    out: list[FusedDecision] = []
    for speaker in speaker_ids:
        key = normalize_diarized_id(speaker) or speaker
        decision = per_speaker[key]
        if key in collided and decision.action == "apply":
            out.append(
                FusedDecision(
                    local_speaker_key=key,
                    action="skip",
                    skip_reason="collision",
                    display_name=decision.display_name,
                    profile_id=decision.profile_id,
                    channels=decision.channels,
                    confidence=decision.confidence,
                    evidence={"collision": True, **decision.evidence},
                )
            )
        else:
            out.append(decision)
    return out


def _fuse_one(
    speaker: str,
    *,
    voice: ChannelCandidate | None,
    mention: ChannelCandidate | None,
    style: ChannelCandidate | None,
    style_only_apply: bool,
) -> FusedDecision:
    channels = tuple(
        c.channel for c in (voice, mention, style) if c is not None
    )
    evidence = {
        "voice": None if voice is None else voice.confidence,
        "mention": None if mention is None else mention.display_name,
        "style": None if style is None else style.confidence,
    }

    if _is_strong(voice) and voice is not None:
        if mention is not None and not (
            _names_agree(voice.display_name, mention.display_name)
            and _profiles_agree(voice.profile_id, mention.profile_id)
        ):
            return FusedDecision(
                local_speaker_key=speaker,
                action="skip",
                skip_reason="conflict",
                display_name=voice.display_name,
                profile_id=voice.profile_id,
                channels=channels,
                confidence=voice.confidence,
                evidence=evidence,
            )
        return FusedDecision(
            local_speaker_key=speaker,
            action="apply",
            display_name=voice.display_name,
            profile_id=voice.profile_id,
            channels=channels,
            confidence=voice.confidence,
            suggestion_id=voice.suggestion_id,
            suggestion_digest=voice.suggestion_digest,
            model_generation_id=voice.model_generation_id,
            evidence=evidence,
        )

    if mention is not None:
        conf = mention.confidence or "possible"
        return FusedDecision(
            local_speaker_key=speaker,
            action="apply",
            display_name=mention.display_name,
            profile_id=mention.profile_id,
            channels=channels,
            confidence=conf,
            evidence=evidence,
        )

    if style_only_apply and _is_strong(style) and style is not None:
        return FusedDecision(
            local_speaker_key=speaker,
            action="apply",
            display_name=style.display_name,
            profile_id=style.profile_id,
            channels=channels,
            confidence=style.confidence,
            evidence=evidence,
        )

    return FusedDecision(
        local_speaker_key=speaker,
        action="skip",
        skip_reason="abstain",
        channels=channels,
        evidence=evidence,
    )
