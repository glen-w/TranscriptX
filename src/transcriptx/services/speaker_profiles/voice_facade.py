"""Streamlit façade for voice analyse / accept behind ActivationBarrier."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from transcriptx.core.speaker_profiles.fingerprint import compute_occurrence_fingerprint
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.voice.acceptance import (
    AcceptSuggestionRequest,
    VoiceAcceptanceOwner,
)
from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
from transcriptx.core.speaker_profiles.voice.match_service import (
    AnalyseResult,
    SpeakerMatchService,
)
from transcriptx.io.speaker_map_resolver import normalize_diarized_id


def voice_session_key(managed_transcript_id: str, local_speaker_key: str, kind: str) -> str:
    return f"voice_{kind}_{managed_transcript_id}_{local_speaker_key}"


def ensure_idempotency_key(session_state: Any, key: str) -> str:
    if key not in session_state or not session_state[key]:
        session_state[key] = str(uuid4())
    return str(session_state[key])


class SpeakerIdVoiceFacade:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or speaker_profiles_dir()
        self.barrier = ActivationBarrier(self.root)
        self.match = SpeakerMatchService(root=self.root)
        self.acceptance = VoiceAcceptanceOwner(root=self.root)

    def status(self):
        return self.barrier.status()

    def analyse(
        self,
        *,
        transcript_path: Path,
        raw_speaker: str,
        segments: list[dict[str, Any]],
    ) -> AnalyseResult:
        resolver = ManagedTranscriptResolver()
        if not resolver.is_managed_path(transcript_path):
            return AnalyseResult(
                outcome="NotManagedTranscript",
                match=None,
                suggestion_id=None,
                suggestion_digest=None,
                detail="managed library only",
            )
        resolved = resolver.resolve_path(transcript_path)
        key = normalize_diarized_id(raw_speaker)
        keyed = [
            s
            for s in segments
            if normalize_diarized_id(str(s.get("speaker") or "")) == key
        ]
        fp = compute_occurrence_fingerprint(keyed)
        return self.match.analyse_occurrence(
            managed_transcript_id=resolved.managed_transcript_id,
            local_speaker_key=key,
            transcript_path=Path(resolved.transcript_path),
            segments=list(segments),
            occurrence_fingerprint=fp,
        )

    def accept(
        self,
        *,
        operation_idempotency_key: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        candidate_profile_id: str,
        suggestion_id: str,
        suggestion_digest: str,
        confidence_category: str,
        model_generation_id: str,
        occurrence_fingerprint: str,
        expected_link_id: str | None = None,
        expected_owner_profile_id: str | None = None,
        expected_fingerprint: str | None = None,
        expected_audio_stat_fingerprint: str | None = None,
        expected_audio_content_sha256: str | None = None,
    ):
        return self.acceptance.accept_suggestion(
            AcceptSuggestionRequest(
                operation_idempotency_key=operation_idempotency_key,
                managed_transcript_id=managed_transcript_id,
                local_speaker_key=local_speaker_key,
                candidate_profile_id=candidate_profile_id,
                suggestion_id=suggestion_id,
                suggestion_digest=suggestion_digest,
                confidence_category=confidence_category,
                model_generation_id=model_generation_id,
                occurrence_fingerprint=occurrence_fingerprint,
                expected_link_id=expected_link_id,
                expected_owner_profile_id=expected_owner_profile_id,
                expected_fingerprint=expected_fingerprint,
                expected_audio_stat_fingerprint=expected_audio_stat_fingerprint,
                expected_audio_content_sha256=expected_audio_content_sha256,
            )
        )

    def reject(
        self,
        *,
        operation_idempotency_key: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        occurrence_fingerprint: str,
        candidate_profile_id: str,
        suggestion_id: str,
        suggestion_digest: str,
        model_generation_id: str,
        reference_corpus_digest: str,
        reference_count: int,
    ):
        return self.acceptance.reject_suggestion(
            operation_idempotency_key=operation_idempotency_key,
            managed_transcript_id=managed_transcript_id,
            local_speaker_key=local_speaker_key,
            occurrence_fingerprint=occurrence_fingerprint,
            candidate_profile_id=candidate_profile_id,
            suggestion_id=suggestion_id,
            suggestion_digest=suggestion_digest,
            model_generation_id=model_generation_id,
            reference_corpus_digest=reference_corpus_digest,
            reference_count=reference_count,
        )

    def bootstrap_enrol_profile(
        self,
        *,
        operation_idempotency_key: str,
        profile_id: str,
    ):
        from transcriptx.core.speaker_profiles.voice.bootstrap import VoiceBootstrapService

        return VoiceBootstrapService(root=self.root).enrol_profile_confirmed_links(
            operation_idempotency_key=operation_idempotency_key,
            profile_id=profile_id,
        )
