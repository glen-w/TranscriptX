"""Bridge: journalled profile create+link then best-effort sidecar naming.

Sidecar naming is intentionally outside the profile operation atomicity barrier.
Naming failure → PartialSuccess with CacheInvalidationSignal for committed parts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from transcriptx.core.speaker_profiles.errors import (
    IgnoredSpeakerLinkError,
    LinkConflictError,
    NotManagedTranscriptError,
    SpeakerProfileContractError,
)
from transcriptx.core.speaker_profiles.identity import (
    link_file_key,
    local_speaker_key_from_raw,
)
from transcriptx.core.speaker_profiles.provenance import LinkProvenanceV1
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import (
    MutationResult,
    SpeakerProfileService,
)
from transcriptx.core.speaker_profiles.signals import CacheInvalidationSignal
from transcriptx.io.speaker_map_resolver import normalize_diarized_id
from transcriptx.services.speaker_studio.controller import SpeakerStudioController


@dataclass(frozen=True)
class PartialSuccess:
    """Profile-store mutation committed; optional naming failure."""

    mutation: MutationResult | None
    naming_ok: bool
    naming_error: str | None = None
    link_already_existed: bool = False
    cache_signal: CacheInvalidationSignal | None = None

    @property
    def is_partial(self) -> bool:
        return (
            self.mutation is not None
            and not self.naming_ok
            and self.naming_error is not None
        )

    @property
    def effective_signal(self) -> CacheInvalidationSignal | None:
        if self.cache_signal is not None:
            return self.cache_signal
        if self.mutation is not None:
            return self.mutation.cache_signal
        return None


def create_profile_link_and_name(
    *,
    transcript_path: str | Path,
    raw_speaker: str,
    display_name: str,
    service: SpeakerProfileService | None = None,
    resolver: ManagedTranscriptResolver | None = None,
    controller: SpeakerStudioController | None = None,
    operation_idempotency_key: str | None = None,
    create_profile: bool = True,
    apply_sidecar_name: bool = True,
    method: str = "web",
) -> PartialSuccess:
    """Managed-only profile link (optional) then best-effort local name.

    When ``create_profile`` is True, ad-hoc / run-output paths raise
    ``NotManagedTranscriptError``. Local naming alone may still proceed when
    ``create_profile`` is False.
    """
    path = Path(transcript_path)
    name = (display_name or "").strip()
    if not name:
        raise SpeakerProfileContractError("display_name must be non-empty")

    local_key = local_speaker_key_from_raw(raw_speaker)
    svc = service or SpeakerProfileService()
    res = resolver or svc.resolver
    studio = controller

    mutation: MutationResult | None = None
    link_already = False
    signal: CacheInvalidationSignal | None = None

    if create_profile:
        try:
            resolved = res.resolve_path(path)
        except Exception as exc:
            raise NotManagedTranscriptError(
                f"profile linking requires a managed library transcript; got {path}"
            ) from exc

        key = link_file_key(resolved.managed_transcript_id, local_key)
        existing = svc.get_live_link(key)
        if existing is not None:
            link_already = True
            signal = CacheInvalidationSignal(
                scopes=("speaker_profiles", "speaker_links"),
                profile_ids=(existing.profile_id,),
                link_ids=(existing.link_id,),
                managed_transcript_ids=(resolved.managed_transcript_id,),
            )
        else:
            try:
                mutation = svc.create_profile_and_link(
                    operation_idempotency_key=operation_idempotency_key or str(uuid4()),
                    display_name=name,
                    managed_transcript_id=resolved.managed_transcript_id,
                    local_speaker_key=local_key,
                    created_by=method,
                )
                signal = mutation.cache_signal
            except IgnoredSpeakerLinkError:
                raise
            except LinkConflictError:
                existing = svc.get_live_link(key)
                link_already = True
                if existing is not None:
                    signal = CacheInvalidationSignal(
                        scopes=("speaker_profiles", "speaker_links"),
                        profile_ids=(existing.profile_id,),
                        link_ids=(existing.link_id,),
                        managed_transcript_ids=(resolved.managed_transcript_id,),
                    )

    naming_ok = True
    naming_error: str | None = None
    if apply_sidecar_name:
        if studio is None:
            studio = SpeakerStudioController()
        try:
            studio.apply_mapping_mutation(
                str(path),
                normalize_diarized_id(raw_speaker) or local_key,
                name,
                method=method,
            )
        except Exception as exc:
            naming_ok = False
            naming_error = str(exc)

    return PartialSuccess(
        mutation=mutation,
        naming_ok=naming_ok,
        naming_error=naming_error,
        link_already_existed=link_already,
        cache_signal=signal,
    )


def link_existing_profile_and_name(
    *,
    transcript_path: str | Path,
    raw_speaker: str,
    display_name: str,
    profile_id: str,
    service: SpeakerProfileService | None = None,
    resolver: ManagedTranscriptResolver | None = None,
    controller: SpeakerStudioController | None = None,
    operation_idempotency_key: str | None = None,
    apply_sidecar_name: bool = True,
    method: str = "web",
    provenance: LinkProvenanceV1 | None = None,
) -> PartialSuccess:
    """Attach an occurrence to an existing profile, then best-effort local name.

    Same-owner live links are a no-op on the profile store. A live link owned by
    a different profile is relinked (explicit target from Speaker ID).
    """
    path = Path(transcript_path)
    name = (display_name or "").strip()
    if not name:
        raise SpeakerProfileContractError("display_name must be non-empty")
    target_id = str(profile_id or "").strip()
    if not target_id:
        raise SpeakerProfileContractError("profile_id must be non-empty")

    local_key = local_speaker_key_from_raw(raw_speaker)
    svc = service or SpeakerProfileService()
    res = resolver or svc.resolver
    studio = controller

    try:
        resolved = res.resolve_path(path)
    except Exception as exc:
        raise NotManagedTranscriptError(
            f"profile linking requires a managed library transcript; got {path}"
        ) from exc

    key = link_file_key(resolved.managed_transcript_id, local_key)
    existing = svc.get_live_link(key)
    mutation: MutationResult | None = None
    link_already = False
    signal: CacheInvalidationSignal | None = None
    op_key = operation_idempotency_key or str(uuid4())
    link_provenance = provenance or LinkProvenanceV1(link_method="choose_other")

    if existing is not None and existing.profile_id == target_id:
        link_already = True
        signal = CacheInvalidationSignal(
            scopes=("speaker_profiles", "speaker_links"),
            profile_ids=(existing.profile_id,),
            link_ids=(existing.link_id,),
            managed_transcript_ids=(resolved.managed_transcript_id,),
        )
    elif existing is not None:
        mutation = svc.relink(
            operation_idempotency_key=op_key,
            managed_transcript_id=resolved.managed_transcript_id,
            local_speaker_key=local_key,
            profile_id=target_id,
            expected_link_id=existing.link_id,
            expected_owner_profile_id=existing.profile_id,
            actor=method,
            provenance=LinkProvenanceV1(
                link_method="relink",
                relinked_from=existing.profile_id,
            ),
        )
        signal = mutation.cache_signal
    else:
        mutation = svc.link_existing_profile(
            operation_idempotency_key=op_key,
            managed_transcript_id=resolved.managed_transcript_id,
            local_speaker_key=local_key,
            profile_id=target_id,
            actor=method,
            provenance=link_provenance,
        )
        signal = mutation.cache_signal

    naming_ok = True
    naming_error: str | None = None
    if apply_sidecar_name:
        if studio is None:
            studio = SpeakerStudioController()
        try:
            studio.apply_mapping_mutation(
                str(path),
                normalize_diarized_id(raw_speaker) or local_key,
                name,
                method=method,
            )
        except Exception as exc:
            naming_ok = False
            naming_error = str(exc)

    return PartialSuccess(
        mutation=mutation,
        naming_ok=naming_ok,
        naming_error=naming_error,
        link_already_existed=link_already,
        cache_signal=signal,
    )
