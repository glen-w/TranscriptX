"""SpeakerProfileService — sole writer for longitudinal speaker profile files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from transcriptx.core.speaker_profiles.discovery import (
    SpeakerOccurrence,
    assert_occurrence_linkable,
    discover_occurrences_for_resolved,
)
from transcriptx.core.speaker_profiles.errors import (
    IgnoredSpeakerLinkError,
    LinkConflictError,
    SpeakerProfileContractError,
    StaleUpdateError,
)
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.layout import (
    speaker_profiles_dir,
    speaker_profiles_lock_path,
)
from transcriptx.core.speaker_profiles.models import (
    SpeakerProfileEventV1,
    SpeakerProfileLinkV1,
    SpeakerProfileV1,
)
from transcriptx.core.speaker_profiles.operations import (
    OperationEngine,
    OperationOutcome,
    PlannedDelete,
    PlannedWrite,
    relative_event_path,
    relative_link_path,
    relative_profile_path,
)
from transcriptx.core.speaker_profiles.recovery import (
    assert_relpath_readable,
    recover_operation,
)
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.signals import CacheInvalidationSignal
from transcriptx.core.speaker_profiles.store_io import (
    dumps_model,
    ensure_layout,
    profile_content_sha256,
    read_live_link,
    read_profile,
    utc_now_iso,
)
from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.paths import PATHS
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    normalize_diarized_id,
)


@dataclass(frozen=True)
class MutationResult:
    """Result of a journalled speaker-profile mutation."""

    outcome: OperationOutcome
    cache_signal: CacheInvalidationSignal
    profile_id: str | None = None
    link_id: str | None = None
    event_ids: tuple[str, ...] = ()


class SpeakerProfileService:
    """All multi-file speaker profile mutations go through this service."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        state_dir: Path | None = None,
        resolver: ManagedTranscriptResolver | None = None,
        speaker_map_resolver: SpeakerMapResolver | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else speaker_profiles_dir()
        self.state_dir = Path(state_dir) if state_dir is not None else PATHS.state_dir
        self.resolver = resolver or ManagedTranscriptResolver()
        self.speaker_map_resolver = speaker_map_resolver or SpeakerMapResolver()
        self.engine = OperationEngine(self.root)

    def _project_lock(self) -> FileLock:
        lock_path = speaker_profiles_lock_path(self.state_dir)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        # FileLock locks the path; use a sentinel file beside the lock name.
        sentinel = lock_path.with_suffix(".lock.target")
        if not sentinel.exists():
            sentinel.write_text("", encoding="utf-8")
        return FileLock(sentinel, timeout=60, blocking=True)

    def get_profile(self, profile_id: str) -> SpeakerProfileV1 | None:
        ensure_layout(self.root)
        assert_relpath_readable(self.root, relative_profile_path(profile_id))
        return read_profile(profile_id, root=self.root)

    def get_live_link(self, link_file_key_value: str) -> SpeakerProfileLinkV1 | None:
        ensure_layout(self.root)
        assert_relpath_readable(self.root, relative_link_path(link_file_key_value))
        return read_live_link(link_file_key_value, root=self.root)

    def recover_operation(self, operation_id: str):
        """Classify and auto-complete / proven-abort a portable operation."""
        ensure_layout(self.root)
        with self._project_lock():
            return recover_operation(self.root, operation_id)

    def create_profile_and_link(
        self,
        *,
        operation_idempotency_key: str,
        display_name: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        notes: str | None = None,
        aliases: list[str] | None = None,
        created_by: str = "user",
    ) -> MutationResult:
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)

            resolved = self.resolver.resolve(managed_transcript_id)
            occurrences = discover_occurrences_for_resolved(resolved)
            occ = self._require_occurrence(occurrences, local_speaker_key)
            assert_occurrence_linkable(occ)
            self._reject_if_ignored(resolved.transcript_path, local_speaker_key)

            key = link_file_key(resolved.managed_transcript_id, local_speaker_key)
            existing = read_live_link(key, root=self.root)
            if existing is not None:
                raise LinkConflictError(
                    f"occurrence already linked to profile {existing.profile_id}"
                )

            now = utc_now_iso()
            profile_id = str(uuid4())
            link_id = str(uuid4())
            event_id = str(uuid4())

            profile = SpeakerProfileV1(
                profile_id=profile_id,
                display_name=display_name.strip(),
                aliases=list(aliases or []),
                notes=notes,
                status="active",
                merged_into_profile_id=None,
                created_at=now,
                updated_at=now,
            )
            link = SpeakerProfileLinkV1(
                link_id=link_id,
                managed_transcript_id=resolved.managed_transcript_id,
                observed_transcript_relpath=resolved.current_relpath,
                local_speaker_key=local_speaker_key,
                profile_id=profile_id,
                status="confirmed",
                occurrence_fingerprint=occ.occurrence_fingerprint,
                observed_label=display_name.strip(),
                created_at=now,
                updated_at=now,
                created_by=created_by,
                provenance={},
            )
            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="link_confirmed",
                created_at=now,
                actor=created_by,
                payload={
                    "profile_id": profile_id,
                    "link_id": link_id,
                    "managed_transcript_id": resolved.managed_transcript_id,
                    "local_speaker_key": local_speaker_key,
                    "created_profile": True,
                },
            )

            outcome = self.engine.run(
                op_type="create_profile_and_link",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_profile_path(profile_id),
                        data=dumps_model(profile),
                    ),
                    PlannedWrite(
                        relpath=relative_link_path(key),
                        data=dumps_model(link),
                    ),
                    PlannedWrite(
                        relpath=relative_event_path(event_id),
                        data=dumps_model(event),
                    ),
                ],
                deletes=[],
                receipt_extra={
                    "profile_id": profile_id,
                    "link_id": link_id,
                    "event_ids": [event_id],
                    "link_file_key": key,
                },
            )
            return MutationResult(
                outcome=outcome,
                profile_id=profile_id,
                link_id=link_id,
                event_ids=(event_id,),
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles", "speaker_links"),
                    profile_ids=(profile_id,),
                    link_ids=(link_id,),
                    managed_transcript_ids=(resolved.managed_transcript_id,),
                ),
            )

    def unlink(
        self,
        *,
        operation_idempotency_key: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        actor: str = "user",
    ) -> MutationResult:
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)

            resolved = self.resolver.resolve(managed_transcript_id)
            key = link_file_key(resolved.managed_transcript_id, local_speaker_key)
            existing = read_live_link(key, root=self.root)
            if existing is None:
                raise SpeakerProfileContractError(
                    f"no live link for occurrence key {key}"
                )

            now = utc_now_iso()
            event_id = str(uuid4())
            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="link_unlinked",
                created_at=now,
                actor=actor,
                payload={
                    "link_id": existing.link_id,
                    "profile_id": existing.profile_id,
                    "managed_transcript_id": existing.managed_transcript_id,
                    "local_speaker_key": existing.local_speaker_key,
                    "link_before": existing.model_dump(mode="python"),
                },
            )
            from transcriptx.core.speaker_profiles.hashing import sha256_file
            from transcriptx.core.speaker_profiles.layout import link_path

            before = sha256_file(link_path(key, root=self.root))
            outcome = self.engine.run(
                op_type="unlink",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_event_path(event_id),
                        data=dumps_model(event),
                    )
                ],
                deletes=[
                    PlannedDelete(
                        relpath=relative_link_path(key),
                        expected_before_sha256=before,
                    )
                ],
                receipt_extra={
                    "profile_id": existing.profile_id,
                    "link_id": existing.link_id,
                    "event_ids": [event_id],
                    "link_file_key": key,
                },
            )
            return MutationResult(
                outcome=outcome,
                profile_id=existing.profile_id,
                link_id=existing.link_id,
                event_ids=(event_id,),
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles", "speaker_links"),
                    profile_ids=(existing.profile_id,),
                    link_ids=(existing.link_id,),
                    managed_transcript_ids=(existing.managed_transcript_id,),
                ),
            )

    def relink(
        self,
        *,
        operation_idempotency_key: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        profile_id: str,
        actor: str = "user",
    ) -> MutationResult:
        """Point an occurrence at an existing active profile (replace live link)."""
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)

            profile = read_profile(profile_id, root=self.root)
            if profile is None:
                raise SpeakerProfileContractError(f"profile not found: {profile_id}")
            if profile.status != "active":
                raise SpeakerProfileContractError(
                    f"cannot link to profile in status {profile.status!r}"
                )

            resolved = self.resolver.resolve(managed_transcript_id)
            occurrences = discover_occurrences_for_resolved(resolved)
            occ = self._require_occurrence(occurrences, local_speaker_key)
            assert_occurrence_linkable(occ)
            self._reject_if_ignored(resolved.transcript_path, local_speaker_key)

            key = link_file_key(resolved.managed_transcript_id, local_speaker_key)
            existing = read_live_link(key, root=self.root)

            now = utc_now_iso()
            link_id = str(uuid4())
            event_id = str(uuid4())
            link = SpeakerProfileLinkV1(
                link_id=link_id,
                managed_transcript_id=resolved.managed_transcript_id,
                observed_transcript_relpath=resolved.current_relpath,
                local_speaker_key=local_speaker_key,
                profile_id=profile_id,
                status="confirmed",
                occurrence_fingerprint=occ.occurrence_fingerprint,
                observed_label=profile.display_name,
                created_at=now,
                updated_at=now,
                created_by=actor,
                provenance={"relinked_from": existing.link_id if existing else None},
            )
            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="link_relinked",
                created_at=now,
                actor=actor,
                payload={
                    "profile_id": profile_id,
                    "link_id": link_id,
                    "previous_link_id": existing.link_id if existing else None,
                    "managed_transcript_id": resolved.managed_transcript_id,
                    "local_speaker_key": local_speaker_key,
                },
            )

            from transcriptx.core.speaker_profiles.hashing import sha256_file
            from transcriptx.core.speaker_profiles.layout import link_path

            before = (
                sha256_file(link_path(key, root=self.root)) if existing is not None else None
            )
            writes = [
                PlannedWrite(
                    relpath=relative_link_path(key),
                    data=dumps_model(link),
                    expected_before_sha256=before,
                ),
                PlannedWrite(
                    relpath=relative_event_path(event_id),
                    data=dumps_model(event),
                ),
            ]
            outcome = self.engine.run(
                op_type="relink",
                operation_idempotency_key=operation_idempotency_key,
                writes=writes,
                deletes=[],
                receipt_extra={
                    "profile_id": profile_id,
                    "link_id": link_id,
                    "event_ids": [event_id],
                    "link_file_key": key,
                },
            )
            return MutationResult(
                outcome=outcome,
                profile_id=profile_id,
                link_id=link_id,
                event_ids=(event_id,),
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles", "speaker_links"),
                    profile_ids=(profile_id,),
                    link_ids=(link_id,),
                    managed_transcript_ids=(resolved.managed_transcript_id,),
                ),
            )

    def update_profile(
        self,
        *,
        operation_idempotency_key: str,
        profile_id: str,
        expected_content_sha256: str,
        display_name: str | None = None,
        aliases: list[str] | None = None,
        notes: str | None = None,
        actor: str = "user",
    ) -> MutationResult:
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)

            current = read_profile(profile_id, root=self.root)
            if current is None:
                raise SpeakerProfileContractError(f"profile not found: {profile_id}")
            actual = profile_content_sha256(profile_id, root=self.root)
            if actual != expected_content_sha256:
                raise StaleUpdateError(
                    f"profile {profile_id} stale: expected {expected_content_sha256}, "
                    f"found {actual}"
                )

            now = utc_now_iso()
            updated = current.model_copy(
                update={
                    "display_name": (
                        display_name.strip()
                        if display_name is not None
                        else current.display_name
                    ),
                    "aliases": (
                        list(aliases) if aliases is not None else list(current.aliases)
                    ),
                    "notes": notes if notes is not None else current.notes,
                    "updated_at": now,
                }
            )
            event_id = str(uuid4())
            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="profile_updated",
                created_at=now,
                actor=actor,
                payload={"profile_id": profile_id},
            )
            outcome = self.engine.run(
                op_type="update_profile",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_profile_path(profile_id),
                        data=dumps_model(updated),
                        expected_before_sha256=expected_content_sha256,
                    ),
                    PlannedWrite(
                        relpath=relative_event_path(event_id),
                        data=dumps_model(event),
                    ),
                ],
                deletes=[],
                receipt_extra={
                    "profile_id": profile_id,
                    "event_ids": [event_id],
                },
            )
            return MutationResult(
                outcome=outcome,
                profile_id=profile_id,
                event_ids=(event_id,),
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles",),
                    profile_ids=(profile_id,),
                ),
            )

    def archive_profile(
        self,
        *,
        operation_idempotency_key: str,
        profile_id: str,
        expected_content_sha256: str,
        actor: str = "user",
    ) -> MutationResult:
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)
            current = read_profile(profile_id, root=self.root)
            if current is None:
                raise SpeakerProfileContractError(f"profile not found: {profile_id}")
            if current.status == "merged":
                raise SpeakerProfileContractError("cannot archive a merged profile")
            actual = profile_content_sha256(profile_id, root=self.root)
            if actual != expected_content_sha256:
                raise StaleUpdateError(
                    f"profile {profile_id} stale: expected {expected_content_sha256}, "
                    f"found {actual}"
                )
            now = utc_now_iso()
            updated = current.model_copy(
                update={"status": "archived", "updated_at": now}
            )
            event_id = str(uuid4())
            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="profile_archived",
                created_at=now,
                actor=actor,
                payload={"profile_id": profile_id},
            )
            outcome = self.engine.run(
                op_type="archive_profile",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_profile_path(profile_id),
                        data=dumps_model(updated),
                        expected_before_sha256=expected_content_sha256,
                    ),
                    PlannedWrite(
                        relpath=relative_event_path(event_id),
                        data=dumps_model(event),
                    ),
                ],
                deletes=[],
                receipt_extra={"profile_id": profile_id, "event_ids": [event_id]},
            )
            return MutationResult(
                outcome=outcome,
                profile_id=profile_id,
                event_ids=(event_id,),
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles",),
                    profile_ids=(profile_id,),
                ),
            )

    def merge_profiles(
        self,
        *,
        operation_idempotency_key: str,
        source_profile_id: str,
        target_profile_id: str,
        expected_source_sha256: str,
        actor: str = "user",
    ) -> MutationResult:
        """Merge source into target: retarget live links, mark source merged."""
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)
            if source_profile_id == target_profile_id:
                raise SpeakerProfileContractError("cannot merge a profile into itself")
            source = read_profile(source_profile_id, root=self.root)
            target = read_profile(target_profile_id, root=self.root)
            if source is None or target is None:
                raise SpeakerProfileContractError("source or target profile missing")
            if target.status != "active":
                raise SpeakerProfileContractError(
                    f"merge target must be active, got {target.status!r}"
                )
            if source.status == "merged":
                # Idempotent: already merged into same target
                if source.merged_into_profile_id == target_profile_id:
                    raise SpeakerProfileContractError(
                        "source already merged into target; use operation replay"
                    )
                raise SpeakerProfileContractError("source profile already merged")
            actual = profile_content_sha256(source_profile_id, root=self.root)
            if actual != expected_source_sha256:
                raise StaleUpdateError(
                    f"source profile stale: expected {expected_source_sha256}, found {actual}"
                )

            from transcriptx.core.speaker_profiles.aggregates import list_profile_links
            from transcriptx.core.speaker_profiles.hashing import sha256_file
            from transcriptx.core.speaker_profiles.layout import link_path
            from transcriptx.core.speaker_profiles.identity import link_file_key as lfk

            links = list_profile_links(source_profile_id, root=self.root)
            now = utc_now_iso()
            event_id = str(uuid4())
            merged = source.model_copy(
                update={
                    "status": "merged",
                    "merged_into_profile_id": target_profile_id,
                    "updated_at": now,
                }
            )
            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="profiles_merged",
                created_at=now,
                actor=actor,
                payload={
                    "source_profile_id": source_profile_id,
                    "target_profile_id": target_profile_id,
                    "retargeted_link_ids": [lnk.link_id for lnk in links],
                },
            )
            writes: list[PlannedWrite] = [
                PlannedWrite(
                    relpath=relative_profile_path(source_profile_id),
                    data=dumps_model(merged),
                    expected_before_sha256=expected_source_sha256,
                ),
                PlannedWrite(
                    relpath=relative_event_path(event_id),
                    data=dumps_model(event),
                ),
            ]
            for lnk in links:
                key = lfk(lnk.managed_transcript_id, lnk.local_speaker_key)
                updated_link = lnk.model_copy(
                    update={"profile_id": target_profile_id, "updated_at": now}
                )
                before = sha256_file(link_path(key, root=self.root))
                writes.append(
                    PlannedWrite(
                        relpath=relative_link_path(key),
                        data=dumps_model(updated_link),
                        expected_before_sha256=before,
                    )
                )
            outcome = self.engine.run(
                op_type="merge_profiles",
                operation_idempotency_key=operation_idempotency_key,
                writes=writes,
                deletes=[],
                receipt_extra={
                    "profile_id": source_profile_id,
                    "target_profile_id": target_profile_id,
                    "event_ids": [event_id],
                },
            )
            return MutationResult(
                outcome=outcome,
                profile_id=source_profile_id,
                event_ids=(event_id,),
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles", "speaker_links"),
                    profile_ids=(source_profile_id, target_profile_id),
                ),
            )

    def supersede_link_fingerprint(
        self,
        *,
        operation_idempotency_key: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        actor: str = "user",
    ) -> MutationResult:
        """Journalled fingerprint supersession after needs_review mismatch."""
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)
            resolved = self.resolver.resolve(managed_transcript_id)
            occurrences = discover_occurrences_for_resolved(resolved)
            occ = self._require_occurrence(occurrences, local_speaker_key)
            key = link_file_key(resolved.managed_transcript_id, local_speaker_key)
            existing = read_live_link(key, root=self.root)
            if existing is None:
                raise SpeakerProfileContractError("no live link to supersede")
            from transcriptx.core.speaker_profiles.hashing import sha256_file
            from transcriptx.core.speaker_profiles.layout import link_path

            now = utc_now_iso()
            updated = existing.model_copy(
                update={
                    "occurrence_fingerprint": occ.occurrence_fingerprint,
                    "updated_at": now,
                }
            )
            event_id = str(uuid4())
            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="link_fingerprint_superseded",
                created_at=now,
                actor=actor,
                payload={
                    "link_id": existing.link_id,
                    "previous_fingerprint": existing.occurrence_fingerprint,
                    "new_fingerprint": occ.occurrence_fingerprint,
                },
            )
            before = sha256_file(link_path(key, root=self.root))
            outcome = self.engine.run(
                op_type="supersede_link_fingerprint",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_link_path(key),
                        data=dumps_model(updated),
                        expected_before_sha256=before,
                    ),
                    PlannedWrite(
                        relpath=relative_event_path(event_id),
                        data=dumps_model(event),
                    ),
                ],
                deletes=[],
                receipt_extra={
                    "profile_id": existing.profile_id,
                    "link_id": existing.link_id,
                    "event_ids": [event_id],
                    "link_file_key": key,
                },
            )
            return MutationResult(
                outcome=outcome,
                profile_id=existing.profile_id,
                link_id=existing.link_id,
                event_ids=(event_id,),
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles", "speaker_links"),
                    profile_ids=(existing.profile_id,),
                    link_ids=(existing.link_id,),
                ),
            )

    def migrate_link_observed_relpath(
        self,
        *,
        operation_idempotency_key: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        actor: str = "user",
    ) -> MutationResult:
        """Explicit migrate op — does not run on read.

        Note: ``observed_transcript_relpath`` is an audit snapshot and is left
        unchanged by design. This op records a migration event and refreshes
        ``updated_at`` only (resolver always returns the current path).
        """
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)
            resolved = self.resolver.resolve(managed_transcript_id)
            key = link_file_key(resolved.managed_transcript_id, local_speaker_key)
            existing = read_live_link(key, root=self.root)
            if existing is None:
                raise SpeakerProfileContractError("no live link to migrate")
            from transcriptx.core.speaker_profiles.hashing import sha256_file
            from transcriptx.core.speaker_profiles.layout import link_path

            now = utc_now_iso()
            # Audit field stays immutable; only updated_at + provenance bump.
            updated = existing.model_copy(
                update={
                    "updated_at": now,
                    "provenance": {
                        **dict(existing.provenance or {}),
                        "migrated_at": now,
                        "resolver_relpath_at_migration": resolved.current_relpath,
                    },
                }
            )
            event_id = str(uuid4())
            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="link_migrated",
                created_at=now,
                actor=actor,
                payload={
                    "link_id": existing.link_id,
                    "observed_transcript_relpath": existing.observed_transcript_relpath,
                    "resolver_relpath": resolved.current_relpath,
                },
            )
            before = sha256_file(link_path(key, root=self.root))
            outcome = self.engine.run(
                op_type="migrate_link",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_link_path(key),
                        data=dumps_model(updated),
                        expected_before_sha256=before,
                    ),
                    PlannedWrite(
                        relpath=relative_event_path(event_id),
                        data=dumps_model(event),
                    ),
                ],
                deletes=[],
                receipt_extra={
                    "profile_id": existing.profile_id,
                    "link_id": existing.link_id,
                    "event_ids": [event_id],
                },
            )
            return MutationResult(
                outcome=outcome,
                profile_id=existing.profile_id,
                link_id=existing.link_id,
                event_ids=(event_id,),
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles", "speaker_links"),
                    profile_ids=(existing.profile_id,),
                    link_ids=(existing.link_id,),
                ),
            )

    def _result_from_receipt(self, outcome: OperationOutcome) -> MutationResult:
        receipt = outcome.receipt
        profile_id = receipt.get("profile_id")
        link_id = receipt.get("link_id")
        event_ids = tuple(receipt.get("event_ids") or ())
        scopes: list[Any] = ["speaker_profiles"]
        if link_id or receipt.get("link_file_key"):
            scopes.append("speaker_links")
        return MutationResult(
            outcome=outcome,
            profile_id=profile_id,
            link_id=link_id,
            event_ids=event_ids,
            cache_signal=CacheInvalidationSignal(
                scopes=tuple(scopes),  # type: ignore[arg-type]
                profile_ids=(profile_id,) if profile_id else (),
                link_ids=(link_id,) if link_id else (),
            ),
        )

    @staticmethod
    def _require_occurrence(
        occurrences: list[SpeakerOccurrence], local_speaker_key: str
    ) -> SpeakerOccurrence:
        for occ in occurrences:
            if occ.local_speaker_key == local_speaker_key:
                return occ
        raise SpeakerProfileContractError(
            f"local_speaker_key {local_speaker_key!r} not found in transcript"
        )

    def _reject_if_ignored(self, transcript_path: Path, local_speaker_key: str) -> None:
        try:
            state = self.speaker_map_resolver.load_mapping(str(transcript_path))
        except Exception:
            return
        ignored = {
            normalize_diarized_id(x)
            for x in (state.ignored_speakers or [])
            if normalize_diarized_id(x)
        }
        if local_speaker_key in ignored:
            raise IgnoredSpeakerLinkError(
                f"cannot link ignored speaker {local_speaker_key!r}"
            )
