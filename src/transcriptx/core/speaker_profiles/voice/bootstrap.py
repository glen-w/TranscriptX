"""Explicit bootstrap enrolment from confirmed profile links."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from transcriptx.core.speaker_profiles.discovery import (
    discover_occurrences_for_resolved,
)
from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.store_io import read_live_link, read_profile
from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
from transcriptx.core.speaker_profiles.voice.audio_resolve import (
    resolve_managed_transcript_audio,
    verify_audio_unchanged,
)
from transcriptx.core.speaker_profiles.voice.excerpt_cache import VoiceExcerptStore
from transcriptx.core.speaker_profiles.voice.excerpts import select_excerpts_v1
from transcriptx.core.speaker_profiles.voice.evidence import (
    EnrolExcerptInput,
    VoiceEvidenceService,
)
from transcriptx.core.speaker_profiles.voice.generations import VoiceGenerationRegistry
from transcriptx.core.speaker_profiles.voice.operator import VoiceOperatorStore
from transcriptx.core.speaker_profiles.voice.runtime import (
    MODEL_ID,
    MODEL_REVISION_PIN,
    ModelUnavailable,
    SpeakerEmbeddingRuntime,
)
from transcriptx.core.speaker_profiles.voice.versioning import (
    BOOTSTRAP_MAX_LINKS_MAX,
    BOOTSTRAP_MAX_LINKS_MIN,
)
from transcriptx.core.utils.paths import PATHS
from transcriptx.io.speaker_map_resolver import normalize_diarized_id


@dataclass(frozen=True)
class BootstrapLinkResult:
    link_file_key: str
    sample_ids: tuple[str, ...]
    outcome: str
    detail: str | None = None


@dataclass(frozen=True)
class BootstrapEnrolResult:
    profile_id: str
    links_attempted: int
    links_enrolled: int
    sample_ids: tuple[str, ...]
    per_link: tuple[BootstrapLinkResult, ...]


class VoiceBootstrapService:
    """Explicit enrol of trusted voice from confirmed links (opt-in alone enrols zero)."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        state_dir: Path | None = None,
        resolver: ManagedTranscriptResolver | None = None,
        runtime: SpeakerEmbeddingRuntime | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else PATHS.speaker_profiles_dir
        self.state_dir = Path(state_dir) if state_dir is not None else PATHS.state_dir
        self.barrier = ActivationBarrier(self.root)
        self.evidence = VoiceEvidenceService(root=self.root, state_dir=self.state_dir)
        self.generations = VoiceGenerationRegistry(self.root)
        self.excerpts = VoiceExcerptStore(self.root)
        self.runtime = runtime or SpeakerEmbeddingRuntime()
        self.resolver = resolver or ManagedTranscriptResolver()

    def enrol_profile_confirmed_links(
        self,
        *,
        operation_idempotency_key: str,
        profile_id: str,
        actor: str = "user",
        require_activation: bool = True,
        max_links: int | None = None,
    ) -> BootstrapEnrolResult:
        if require_activation:
            self.barrier.assert_processing_allowed()
        profile = read_profile(profile_id, root=self.root)
        if profile is None:
            raise SpeakerProfileContractError(f"profile not found: {profile_id}")
        if profile.status != "active":
            raise SpeakerProfileContractError(
                f"cannot enrol voice for profile status {profile.status!r}"
            )

        if max_links is None:
            max_links = VoiceOperatorStore(self.root).read().bootstrap_max_links
        if not (BOOTSTRAP_MAX_LINKS_MIN <= max_links <= BOOTSTRAP_MAX_LINKS_MAX):
            raise SpeakerProfileContractError(
                "max_links must be between "
                f"{BOOTSTRAP_MAX_LINKS_MIN} and {BOOTSTRAP_MAX_LINKS_MAX}"
            )

        pin = self.generations.ensure_default_generation_and_activate(
            operation_idempotency_key=f"{operation_idempotency_key}:gen"
        )
        model_generation_id = pin.model_generation_id

        links_dir = self.root / "links"
        candidates: list[tuple[str, object]] = []
        if links_dir.is_dir():
            for path in sorted(links_dir.glob("*.speaker_link.json")):
                stem = path.name[: -len(".speaker_link.json")]
                link = read_live_link(stem, root=self.root)
                if link is None or link.profile_id != profile_id:
                    continue
                if link.status != "confirmed":
                    continue
                candidates.append((stem, link))
                if len(candidates) >= max_links:
                    break

        per_link: list[BootstrapLinkResult] = []
        all_samples: list[str] = []
        enrolled = 0
        for i, (key, link) in enumerate(candidates):
            try:
                result = self._enrol_one_link(
                    operation_idempotency_key=f"{operation_idempotency_key}:link:{i}",
                    link_file_key_value=key,
                    model_generation_id=model_generation_id,
                    actor=actor,
                    require_activation=require_activation,
                )
                per_link.append(result)
                if result.sample_ids:
                    enrolled += 1
                    all_samples.extend(result.sample_ids)
            except ModelUnavailable as exc:
                per_link.append(
                    BootstrapLinkResult(
                        link_file_key=key,
                        sample_ids=(),
                        outcome="ModelUnavailable",
                        detail=str(exc),
                    )
                )
            except Exception as exc:
                per_link.append(
                    BootstrapLinkResult(
                        link_file_key=key,
                        sample_ids=(),
                        outcome="EnrolFailed",
                        detail=str(exc),
                    )
                )

        return BootstrapEnrolResult(
            profile_id=profile_id,
            links_attempted=len(candidates),
            links_enrolled=enrolled,
            sample_ids=tuple(all_samples),
            per_link=tuple(per_link),
        )

    def _enrol_one_link(
        self,
        *,
        operation_idempotency_key: str,
        link_file_key_value: str,
        model_generation_id: str,
        actor: str,
        require_activation: bool,
    ) -> BootstrapLinkResult:
        link = read_live_link(link_file_key_value, root=self.root)
        if link is None:
            return BootstrapLinkResult(
                link_file_key=link_file_key_value,
                sample_ids=(),
                outcome="NoLiveLink",
            )
        resolved = self.resolver.resolve(link.managed_transcript_id)
        occurrences = discover_occurrences_for_resolved(resolved)
        occ = next(
            (
                o
                for o in occurrences
                if normalize_diarized_id(o.local_speaker_key)
                == normalize_diarized_id(link.local_speaker_key)
            ),
            None,
        )
        if occ is None:
            return BootstrapLinkResult(
                link_file_key=link_file_key_value,
                sample_ids=(),
                outcome="OccurrenceMissing",
            )
        # Load segments from resolved transcript for excerpt selection
        import json

        doc = json.loads(Path(resolved.transcript_path).read_text(encoding="utf-8"))
        segments = list(doc.get("segments") or [])
        selection = select_excerpts_v1(
            segments,
            local_speaker_key=link.local_speaker_key,
            normalize_speaker=normalize_diarized_id,
        )
        if selection.outcome != "ok":
            return BootstrapLinkResult(
                link_file_key=link_file_key_value,
                sample_ids=(),
                outcome=selection.outcome,
            )

        audio = resolve_managed_transcript_audio(Path(resolved.transcript_path))
        wav_paths = [
            self.excerpts.get_or_extract(
                audio_path=audio.audio_path,
                audio_content_sha256=audio.audio_content_sha256,
                plan=plan,
                model_generation_id=model_generation_id,
            )
            for plan in selection.excerpts
        ]
        verify_audio_unchanged(audio)
        from dataclasses import asdict

        batch = self.runtime.embed_wav_paths(wav_paths)
        runtime_meta = asdict(batch.meta)
        excerpts = [
            EnrolExcerptInput(
                clip_start_us=plan.start_us,
                clip_end_us=plan.end_us,
                audio_stat_fingerprint=audio.audio_stat_fingerprint,
                audio_content_sha256=audio.audio_content_sha256,
                vector=vec,
                runtime_metadata=runtime_meta,
                model_id=MODEL_ID,
                model_revision=MODEL_REVISION_PIN,
                model_generation_id=model_generation_id,
            )
            for plan, vec in zip(selection.excerpts, batch.vectors)
        ]
        enrolled = self.evidence.enrol_trusted_excerpts_from_link(
            operation_idempotency_key=operation_idempotency_key,
            link_file_key_value=link_file_key_value,
            excerpts=excerpts,
            actor=actor,
            require_activation=require_activation,
        )
        return BootstrapLinkResult(
            link_file_key=link_file_key_value,
            sample_ids=enrolled.sample_ids,
            outcome="Enrolled",
        )
