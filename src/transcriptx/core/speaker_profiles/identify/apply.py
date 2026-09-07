"""Apply fused decisions to speaker maps and/or profile links (no voice enrol)."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.speaker_profiles.identify.models import (
    FusedDecision,
    SpeakerApplyResult,
)
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.provenance import LinkProvenanceV1
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.store_io import read_live_link
from transcriptx.io.speaker_map_resolver import (
    is_effective_speaker_name,
    normalize_diarized_id,
)
from transcriptx.services.speaker_studio.mapping_service import SpeakerMappingService


def apply_decisions(
    *,
    transcript_path: Path,
    managed_transcript_id: str | None,
    decisions: list[FusedDecision],
    auto_name: bool,
    auto_link: bool,
    dry_run: bool,
    mapping: SpeakerMappingService | None = None,
    profiles: SpeakerProfileService | None = None,
    profiles_root: Path | None = None,
) -> list[SpeakerApplyResult]:
    mapper = mapping or SpeakerMappingService()
    profile_svc = profiles
    state = mapper.get_mapping(str(transcript_path))
    ignored = set(state.ignored_speakers)
    out: list[SpeakerApplyResult] = []
    for decision in decisions:
        key = normalize_diarized_id(decision.local_speaker_key)
        existing_name = state.speaker_map.get(key, "")
        already_named = is_effective_speaker_name(key, existing_name)
        is_ignored = key in ignored
        live = None
        if managed_transcript_id and profiles_root is not None:
            try:
                live = read_live_link(
                    link_file_key(managed_transcript_id, key),
                    root=profiles_root,
                )
            except Exception:
                live = None

        if is_ignored:
            out.append(
                SpeakerApplyResult(
                    local_speaker_key=key,
                    skipped_name_reason="ignored",
                    skipped_link_reason="ignored",
                )
            )
            continue

        named = False
        linked = False
        skip_name = None
        skip_link = None
        error = None

        if decision.action != "apply":
            skip_name = decision.skip_reason or "abstain"
            skip_link = decision.skip_reason or "abstain"
            out.append(
                SpeakerApplyResult(
                    local_speaker_key=key,
                    skipped_name_reason=skip_name,
                    skipped_link_reason=skip_link,
                    display_name=decision.display_name,
                    profile_id=decision.profile_id,
                )
            )
            continue

        if auto_name:
            if already_named:
                skip_name = "already_named"
            elif not decision.display_name:
                skip_name = "abstain"
            elif dry_run:
                named = True
            else:
                try:
                    mapper.assign_speaker(
                        str(transcript_path),
                        key,
                        decision.display_name,
                        method="auto_identified",
                        speaker_map_source={
                            "kind": "auto_identified",
                            "channels": list(decision.channels),
                            "confidence": decision.confidence,
                        },
                    )
                    named = True
                    already_named = True
                    state = mapper.get_mapping(str(transcript_path))
                except Exception as exc:
                    error = str(exc)
                    skip_name = "error"
        else:
            skip_name = "auto_name_off"

        if auto_link:
            if live is not None:
                skip_link = "already_linked"
            elif not decision.profile_id:
                skip_link = "no_profile"
            elif not managed_transcript_id:
                skip_link = "not_managed"
            elif dry_run:
                linked = True
            else:
                if profile_svc is None:
                    profile_svc = SpeakerProfileService(root=profiles_root)
                try:
                    provenance = LinkProvenanceV1(
                        link_method="auto_identified",
                        suggestion_id=decision.suggestion_id,
                        suggestion_digest=decision.suggestion_digest,
                        model_generation_id=decision.model_generation_id,
                        confidence_category=(
                            decision.confidence
                            if decision.confidence in ("strong", "possible", "weak")
                            else None
                        ),
                    )
                    profile_svc.link_existing_profile(
                        operation_idempotency_key=(
                            f"auto-identify:{managed_transcript_id}:{key}:"
                            f"{decision.profile_id}"
                        ),
                        managed_transcript_id=managed_transcript_id,
                        local_speaker_key=key,
                        profile_id=decision.profile_id,
                        actor="auto_identify",
                        provenance=provenance,
                    )
                    linked = True
                except Exception as exc:
                    error = str(exc) if error is None else error
                    skip_link = "error"
        else:
            skip_link = "auto_link_off"

        out.append(
            SpeakerApplyResult(
                local_speaker_key=key,
                named=named,
                linked=linked,
                skipped_name_reason=skip_name,
                skipped_link_reason=skip_link,
                display_name=decision.display_name,
                profile_id=decision.profile_id,
                error=error,
            )
        )
    return out
