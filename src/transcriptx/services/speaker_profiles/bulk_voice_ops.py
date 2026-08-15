"""Library-wide voice enrol and suggestion pre-load for Settings → Speakers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

from transcriptx.core.speaker_profiles.aggregates import list_profiles
from transcriptx.core.speaker_profiles.discovery import (
    discover_occurrences_for_resolved,
)
from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
from transcriptx.core.speaker_profiles.resolver import (
    ManagedTranscriptResolver,
    load_transcript_segments,
)
from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
from transcriptx.core.speaker_profiles.voice.inventory import list_samples_for_profile
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    normalize_diarized_id,
)
from transcriptx.services.speaker_profiles.voice_facade import SpeakerIdVoiceFacade

ProgressCallback = Callable[[int, int, str], None]


class BulkVoiceTargetStatus(str, Enum):
    OK = "ok"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True)
class BulkEnrolProfilePreview:
    profile_id: str
    display_name: str
    link_count: int
    eligible_sample_count: int
    actionable: bool


@dataclass(frozen=True)
class BulkEnrolPreview:
    profile_count: int
    with_confirmed_links: int
    without_confirmed_links: int
    with_eligible_samples: int
    actionable_count: int
    targets: list[BulkEnrolProfilePreview] = field(default_factory=list)


@dataclass(frozen=True)
class BulkEnrolProfileResult:
    profile_id: str
    display_name: str
    status: BulkVoiceTargetStatus
    links_attempted: int = 0
    links_enrolled: int = 0
    sample_count: int = 0
    message: str = ""


@dataclass(frozen=True)
class BulkEnrolResult:
    targets: list[BulkEnrolProfileResult] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkVoiceTargetStatus.OK)

    @property
    def skipped_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkVoiceTargetStatus.SKIPPED)

    @property
    def error_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkVoiceTargetStatus.ERROR)

    @property
    def links_enrolled_total(self) -> int:
        return sum(t.links_enrolled for t in self.targets)

    @property
    def samples_total(self) -> int:
        return sum(t.sample_count for t in self.targets)


@dataclass(frozen=True)
class BulkPreloadOccurrencePreview:
    managed_transcript_id: str
    transcript_path: str
    transcript_label: str
    local_speaker_key: str
    ignored: bool = False
    collision: bool = False
    actionable: bool = True


@dataclass(frozen=True)
class BulkPreloadPreview:
    transcript_count: int
    occurrence_count: int
    ignored_count: int
    collision_count: int
    actionable_count: int
    targets: list[BulkPreloadOccurrencePreview] = field(default_factory=list)


@dataclass(frozen=True)
class BulkPreloadOccurrenceResult:
    managed_transcript_id: str
    transcript_label: str
    local_speaker_key: str
    status: BulkVoiceTargetStatus
    outcome: str = ""
    message: str = ""


@dataclass(frozen=True)
class BulkPreloadResult:
    targets: list[BulkPreloadOccurrenceResult] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkVoiceTargetStatus.OK)

    @property
    def skipped_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkVoiceTargetStatus.SKIPPED)

    @property
    def error_count(self) -> int:
        return sum(1 for t in self.targets if t.status is BulkVoiceTargetStatus.ERROR)

    @property
    def suggestion_count(self) -> int:
        return sum(1 for t in self.targets if t.outcome == "SuggestionAvailable")

    @property
    def no_match_count(self) -> int:
        return sum(1 for t in self.targets if t.outcome == "NoReliableMatch")


def _transcript_label(path: Path) -> str:
    return path.stem or path.name


def _ignored_keys_for_path(transcript_path: Path) -> set[str]:
    try:
        state = SpeakerMapResolver().load_mapping(str(transcript_path))
    except Exception:
        return set()
    return {
        normalize_diarized_id(x)
        for x in (state.ignored_speakers or [])
        if normalize_diarized_id(x)
    }


class BulkVoiceOpsService:
    """Settings batch ops: enrol all active profiles; pre-load suggestions library-wide."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        facade: SpeakerIdVoiceFacade | None = None,
        resolver: ManagedTranscriptResolver | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else speaker_profiles_dir()
        self.facade = facade or SpeakerIdVoiceFacade(root=self.root)
        self.resolver = resolver or ManagedTranscriptResolver()
        self.barrier = ActivationBarrier(self.root)

    def preview_enrol_all_profiles(self) -> BulkEnrolPreview:
        self.barrier.assert_processing_allowed()
        targets: list[BulkEnrolProfilePreview] = []
        with_links = 0
        without_links = 0
        with_eligible = 0
        for item in list_profiles(root=self.root):
            if item.status != "active":
                continue
            samples = list_samples_for_profile(item.profile_id, root=self.root)
            eligible = sum(1 for s in samples if s.eligibility_state == "eligible")
            actionable = item.link_count > 0
            if item.link_count > 0:
                with_links += 1
            else:
                without_links += 1
            if eligible > 0:
                with_eligible += 1
            targets.append(
                BulkEnrolProfilePreview(
                    profile_id=item.profile_id,
                    display_name=item.display_name,
                    link_count=item.link_count,
                    eligible_sample_count=eligible,
                    actionable=actionable,
                )
            )
        return BulkEnrolPreview(
            profile_count=len(targets),
            with_confirmed_links=with_links,
            without_confirmed_links=without_links,
            with_eligible_samples=with_eligible,
            actionable_count=sum(1 for t in targets if t.actionable),
            targets=targets,
        )

    def enrol_all_profiles(
        self,
        *,
        operation_idempotency_key: str | None = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkEnrolResult:
        preview = self.preview_enrol_all_profiles()
        base_key = operation_idempotency_key or str(uuid4())
        results: list[BulkEnrolProfileResult] = []
        total = len(preview.targets)
        for index, target in enumerate(preview.targets, start=1):
            label = target.display_name or target.profile_id
            if progress_callback is not None:
                progress_callback(index, total, label)
            if not target.actionable:
                results.append(
                    BulkEnrolProfileResult(
                        profile_id=target.profile_id,
                        display_name=target.display_name,
                        status=BulkVoiceTargetStatus.SKIPPED,
                        message="No confirmed links",
                    )
                )
                continue
            try:
                enrol = self.facade.bootstrap_enrol_profile(
                    operation_idempotency_key=f"{base_key}:{target.profile_id}",
                    profile_id=target.profile_id,
                )
                results.append(
                    BulkEnrolProfileResult(
                        profile_id=target.profile_id,
                        display_name=target.display_name,
                        status=BulkVoiceTargetStatus.OK,
                        links_attempted=int(enrol.links_attempted),
                        links_enrolled=int(enrol.links_enrolled),
                        sample_count=len(enrol.sample_ids),
                    )
                )
            except Exception as exc:
                results.append(
                    BulkEnrolProfileResult(
                        profile_id=target.profile_id,
                        display_name=target.display_name,
                        status=BulkVoiceTargetStatus.ERROR,
                        message=str(exc),
                    )
                )
        return BulkEnrolResult(targets=results)

    def preview_preload_suggestions(self) -> BulkPreloadPreview:
        self.barrier.assert_processing_allowed()
        admitted = self.resolver.list_admitted()
        targets: list[BulkPreloadOccurrencePreview] = []
        ignored_count = 0
        collision_count = 0
        for resolved in admitted:
            path = Path(resolved.transcript_path)
            label = _transcript_label(path)
            ignored = _ignored_keys_for_path(path)
            try:
                occurrences = discover_occurrences_for_resolved(resolved)
            except Exception:
                continue
            for occ in occurrences:
                is_ignored = occ.local_speaker_key in ignored
                is_collision = bool(occ.collision)
                actionable = not is_ignored and not is_collision
                if is_ignored:
                    ignored_count += 1
                if is_collision:
                    collision_count += 1
                targets.append(
                    BulkPreloadOccurrencePreview(
                        managed_transcript_id=resolved.managed_transcript_id,
                        transcript_path=str(path),
                        transcript_label=label,
                        local_speaker_key=occ.local_speaker_key,
                        ignored=is_ignored,
                        collision=is_collision,
                        actionable=actionable,
                    )
                )
        actionable_count = sum(1 for t in targets if t.actionable)
        return BulkPreloadPreview(
            transcript_count=len(admitted),
            occurrence_count=len(targets),
            ignored_count=ignored_count,
            collision_count=collision_count,
            actionable_count=actionable_count,
            targets=targets,
        )

    def preload_suggestions(
        self,
        *,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkPreloadResult:
        preview = self.preview_preload_suggestions()
        results: list[BulkPreloadOccurrenceResult] = []
        actionable = [t for t in preview.targets if t.actionable]
        total = len(actionable)
        index = 0
        segments_cache: dict[str, list[dict]] = {}

        for target in preview.targets:
            if not target.actionable:
                reason = "Ignored" if target.ignored else "Collision"
                if target.ignored and target.collision:
                    reason = "Ignored and collision"
                results.append(
                    BulkPreloadOccurrenceResult(
                        managed_transcript_id=target.managed_transcript_id,
                        transcript_label=target.transcript_label,
                        local_speaker_key=target.local_speaker_key,
                        status=BulkVoiceTargetStatus.SKIPPED,
                        message=reason,
                    )
                )
                continue

            index += 1
            label = f"{target.transcript_label} / {target.local_speaker_key}"
            if progress_callback is not None:
                progress_callback(index, total, label)

            try:
                if target.transcript_path not in segments_cache:
                    segments_cache[target.transcript_path] = load_transcript_segments(
                        target.transcript_path
                    )
                segments = segments_cache[target.transcript_path]
                analyse = self.facade.analyse(
                    transcript_path=Path(target.transcript_path),
                    raw_speaker=target.local_speaker_key,
                    segments=segments,
                )
                results.append(
                    BulkPreloadOccurrenceResult(
                        managed_transcript_id=target.managed_transcript_id,
                        transcript_label=target.transcript_label,
                        local_speaker_key=target.local_speaker_key,
                        status=BulkVoiceTargetStatus.OK,
                        outcome=str(analyse.outcome or ""),
                        message=str(analyse.detail or ""),
                    )
                )
            except Exception as exc:
                results.append(
                    BulkPreloadOccurrenceResult(
                        managed_transcript_id=target.managed_transcript_id,
                        transcript_label=target.transcript_label,
                        local_speaker_key=target.local_speaker_key,
                        status=BulkVoiceTargetStatus.ERROR,
                        message=str(exc),
                    )
                )
        return BulkPreloadResult(targets=results)
