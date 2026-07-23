"""SpeakerProfileService — sole writer for longitudinal speaker profile files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from transcriptx.core.speaker_profiles.accents import assign_unused_accent
from transcriptx.core.speaker_profiles.discovery import (
    SpeakerOccurrence,
    assert_occurrence_linkable,
    discover_occurrences_for_resolved,
)
from transcriptx.core.speaker_profiles.errors import (
    IgnoredSpeakerLinkError,
    LinkConflictError,
    SpeakerProfileContractError,
    StaleConfirmationError,
    StaleUpdateError,
)
from transcriptx.core.speaker_profiles.hashing import sha256_file
from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.layout import (
    link_path,
    profiles_dir,
    speaker_profiles_dir,
    speaker_profiles_lock_path,
)
from transcriptx.core.speaker_profiles.models import (
    SpeakerProfileEventV1,
    SpeakerProfileLinkV1,
    SpeakerProfileV1,
)
from transcriptx.core.speaker_profiles.normalize import (
    apply_profile_update,
    normalize_profile_fields,
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
    OperationRecoveryReport,
    affected_relpaths,
    assert_relpath_readable,
    recover_operation as recover_operation_impl,
)
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.signals import CacheInvalidationSignal
from transcriptx.core.speaker_profiles.store_io import (
    dumps_model,
    ensure_layout,
    load_operation,
    parse_model,
    profile_content_sha256,
    read_live_link,
    read_profile,
    utc_now_iso,
)
from transcriptx.core.speaker_profiles.versioning import (
    LINK_FILE_SUFFIX,
    PROFILE_FILE_SUFFIX,
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
    noop: bool = False


@dataclass(frozen=True)
class RecoveryResult:
    """Result of classifying / completing a portable operation."""

    report: OperationRecoveryReport
    cache_signal: CacheInvalidationSignal


def _noop_result(
    op_type: str,
    operation_idempotency_key: str,
    **ids: Any,
) -> MutationResult:
    """Return a no-journal MutationResult when the store is already current."""
    profile_id = ids.get("profile_id")
    link_id = ids.get("link_id")
    event_ids = tuple(ids.get("event_ids") or ())
    profile_ids = tuple(
        ids.get("profile_ids")
        or ((profile_id,) if profile_id else ())
    )
    link_ids = tuple(
        ids.get("link_ids") or ((link_id,) if link_id else ())
    )
    managed_transcript_ids = tuple(ids.get("managed_transcript_ids") or ())
    scopes: list[str] = ["speaker_profiles"]
    if link_ids or ids.get("link_file_key") or ids.get("link_id"):
        scopes.append("speaker_links")
    receipt: dict[str, Any] = {
        "noop": True,
        "op_type": op_type,
        "operation_idempotency_key": operation_idempotency_key,
        "profile_ids": list(profile_ids),
        "link_ids": list(link_ids),
        "managed_transcript_ids": list(managed_transcript_ids),
        "scopes": list(scopes),
    }
    for key, value in ids.items():
        if key not in receipt:
            receipt[key] = value
    if profile_id is not None:
        receipt.setdefault("profile_id", profile_id)
    if link_id is not None:
        receipt.setdefault("link_id", link_id)
    return MutationResult(
        outcome=OperationOutcome(
            operation_id="noop",
            operation_idempotency_key=operation_idempotency_key,
            op_type=op_type,
            replayed=False,
            receipt=receipt,
        ),
        cache_signal=CacheInvalidationSignal(
            scopes=tuple(scopes),  # type: ignore[arg-type]
            profile_ids=profile_ids,
            link_ids=link_ids,
            managed_transcript_ids=managed_transcript_ids,
        ),
        profile_id=profile_id,
        link_id=link_id,
        event_ids=event_ids,
        noop=True,
    )


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

    def _assert_entities_readable(
        self,
        *,
        profile_ids: tuple[str, ...] | list[str] = (),
        link_file_keys: tuple[str, ...] | list[str] = (),
    ) -> None:
        """Fail closed when profile/link paths intersect blocking ops (caller holds lock)."""
        for profile_id in profile_ids:
            assert_relpath_readable(self.root, relative_profile_path(profile_id))
        for key in link_file_keys:
            assert_relpath_readable(self.root, relative_link_path(key))

    def _active_accent_colors(self) -> list[str | None]:
        """Accent colours currently claimed by active profiles."""
        colors: list[str | None] = []
        root = profiles_dir(self.root)
        if not root.is_dir():
            return colors
        for path in sorted(root.glob(f"*{PROFILE_FILE_SUFFIX}")):
            try:
                profile = parse_model(SpeakerProfileV1, path)
            except Exception:
                continue
            if profile.status == "active":
                colors.append(profile.accent_color)
        return colors

    def get_profile(self, profile_id: str) -> SpeakerProfileV1 | None:
        ensure_layout(self.root)
        assert_relpath_readable(self.root, relative_profile_path(profile_id))
        return read_profile(profile_id, root=self.root)

    def get_live_link(self, link_file_key_value: str) -> SpeakerProfileLinkV1 | None:
        ensure_layout(self.root)
        assert_relpath_readable(self.root, relative_link_path(link_file_key_value))
        return read_live_link(link_file_key_value, root=self.root)

    def recover_operation(self, operation_id: str) -> RecoveryResult:
        """Classify and auto-complete / proven-abort a portable operation."""
        ensure_layout(self.root)
        with self._project_lock():
            report = recover_operation_impl(self.root, operation_id)
            from transcriptx.core.speaker_profiles.layout import operation_path

            op = load_operation(operation_path(operation_id, root=self.root))
            profile_ids: list[str] = []
            link_ids: list[str] = []
            for rel in sorted(affected_relpaths(op)):
                name = Path(rel).name
                if rel.startswith("profiles/") and name.endswith(PROFILE_FILE_SUFFIX):
                    profile_ids.append(name[: -len(PROFILE_FILE_SUFFIX)])
                elif rel.startswith("links/") and name.endswith(LINK_FILE_SUFFIX):
                    link_ids.append(name[: -len(LINK_FILE_SUFFIX)])
            return RecoveryResult(
                report=report,
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles", "speaker_links"),
                    profile_ids=tuple(dict.fromkeys(profile_ids)),
                    link_ids=tuple(dict.fromkeys(link_ids)),
                ),
            )

    def create_profile_and_link(
        self,
        *,
        operation_idempotency_key: str,
        display_name: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        notes: str | None = None,
        aliases: list[str] | None = None,
        accent_color: str | None = None,
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
            self._assert_entities_readable(link_file_keys=(key,))

            existing = read_live_link(key, root=self.root)
            if existing is not None:
                raise LinkConflictError(
                    f"occurrence already linked to profile {existing.profile_id}"
                )

            chosen_accent = (
                accent_color
                if accent_color is not None
                else assign_unused_accent(self._active_accent_colors())
            )
            fields = normalize_profile_fields(
                display_name=display_name,
                aliases=aliases,
                notes=notes,
                accent_color=chosen_accent,
            )

            now = utc_now_iso()
            profile_id = str(uuid4())
            link_id = str(uuid4())
            event_id = str(uuid4())

            self._assert_entities_readable(
                profile_ids=(profile_id,),
                link_file_keys=(key,),
            )

            profile = SpeakerProfileV1(
                profile_id=profile_id,
                display_name=fields.display_name,
                aliases=list(fields.aliases),
                notes=fields.notes,
                accent_color=fields.accent_color,
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
                observed_label=fields.display_name,
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

            scopes = ["speaker_profiles", "speaker_links"]
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
                    "profile_ids": [profile_id],
                    "link_ids": [link_id],
                    "managed_transcript_ids": [resolved.managed_transcript_id],
                    "scopes": scopes,
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
        expected_link_id: str | None = None,
        expected_link_sha256: str | None = None,
        actor: str = "user",
    ) -> MutationResult:
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)

            resolved = self.resolver.resolve(managed_transcript_id)
            key = link_file_key(resolved.managed_transcript_id, local_speaker_key)
            self._assert_entities_readable(link_file_keys=(key,))

            existing = read_live_link(key, root=self.root)
            if existing is None:
                raise SpeakerProfileContractError(
                    f"no live link for occurrence key {key}"
                )

            self._assert_entities_readable(
                profile_ids=(existing.profile_id,),
                link_file_keys=(key,),
            )
            self._assert_expected_link(
                existing,
                link_file_key_value=key,
                expected_link_id=expected_link_id,
                expected_link_sha256=expected_link_sha256,
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
            before = sha256_file(link_path(key, root=self.root))
            scopes = ["speaker_profiles", "speaker_links"]
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
                    "profile_ids": [existing.profile_id],
                    "link_ids": [existing.link_id],
                    "managed_transcript_ids": [existing.managed_transcript_id],
                    "scopes": scopes,
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

    def link_existing_profile(
        self,
        *,
        operation_idempotency_key: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        profile_id: str,
        actor: str = "user",
    ) -> MutationResult:
        """Link an unlinked occurrence to an existing active profile."""
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)

            resolved = self.resolver.resolve(managed_transcript_id)
            key = link_file_key(resolved.managed_transcript_id, local_speaker_key)

            self._assert_entities_readable(
                profile_ids=(profile_id,),
                link_file_keys=(key,),
            )

            profile = read_profile(profile_id, root=self.root)
            if profile is None:
                raise SpeakerProfileContractError(f"profile not found: {profile_id}")
            if profile.status != "active":
                raise SpeakerProfileContractError(
                    f"cannot link to profile in status {profile.status!r}"
                )

            existing = read_live_link(key, root=self.root)
            if existing is not None:
                raise SpeakerProfileContractError(
                    "occurrence already has a live link; use relink"
                )

            occurrences = discover_occurrences_for_resolved(resolved)
            occ = self._require_occurrence(occurrences, local_speaker_key)
            assert_occurrence_linkable(occ)
            self._reject_if_ignored(resolved.transcript_path, local_speaker_key)

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
                provenance={},
            )
            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="link_confirmed",
                created_at=now,
                actor=actor,
                payload={
                    "profile_id": profile_id,
                    "link_id": link_id,
                    "managed_transcript_id": resolved.managed_transcript_id,
                    "local_speaker_key": local_speaker_key,
                    "created_profile": False,
                },
            )
            scopes = ["speaker_profiles", "speaker_links"]
            outcome = self.engine.run(
                op_type="link_existing_profile",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
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
                    "profile_ids": [profile_id],
                    "link_ids": [link_id],
                    "managed_transcript_ids": [resolved.managed_transcript_id],
                    "scopes": scopes,
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

    def relink(
        self,
        *,
        operation_idempotency_key: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        profile_id: str,
        expected_link_id: str | None = None,
        expected_owner_profile_id: str | None = None,
        expected_link_sha256: str | None = None,
        actor: str = "user",
    ) -> MutationResult:
        """Replace an existing live link's owner profile."""
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
                    "no live link for occurrence; use link_existing_profile"
                )

            self._assert_entities_readable(
                profile_ids=(profile_id, existing.profile_id),
                link_file_keys=(key,),
            )

            profile = read_profile(profile_id, root=self.root)
            if profile is None:
                raise SpeakerProfileContractError(f"profile not found: {profile_id}")
            if profile.status != "active":
                raise SpeakerProfileContractError(
                    f"cannot link to profile in status {profile.status!r}"
                )

            self._assert_expected_link(
                existing,
                link_file_key_value=key,
                expected_link_id=expected_link_id,
                expected_link_sha256=expected_link_sha256,
                expected_owner_profile_id=expected_owner_profile_id,
            )

            if existing.profile_id == profile_id:
                return _noop_result(
                    "relink",
                    operation_idempotency_key,
                    profile_id=profile_id,
                    link_id=existing.link_id,
                    profile_ids=[existing.profile_id, profile_id],
                    link_ids=[existing.link_id],
                    managed_transcript_ids=[resolved.managed_transcript_id],
                    link_file_key=key,
                )

            occurrences = discover_occurrences_for_resolved(resolved)
            occ = self._require_occurrence(occurrences, local_speaker_key)
            assert_occurrence_linkable(occ)
            self._reject_if_ignored(resolved.transcript_path, local_speaker_key)

            now = utc_now_iso()
            link_id = str(uuid4())
            event_id = str(uuid4())
            previous_link_id = existing.link_id
            previous_profile_id = existing.profile_id
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
                provenance={"relinked_from": previous_link_id},
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
                    "previous_link_id": previous_link_id,
                    "previous_profile_id": previous_profile_id,
                    "managed_transcript_id": resolved.managed_transcript_id,
                    "local_speaker_key": local_speaker_key,
                },
            )

            before = sha256_file(link_path(key, root=self.root))
            scopes = ["speaker_profiles", "speaker_links"]
            profile_ids = list(
                dict.fromkeys([previous_profile_id, profile_id])
            )
            outcome = self.engine.run(
                op_type="relink",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_link_path(key),
                        data=dumps_model(link),
                        expected_before_sha256=before,
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
                    "profile_ids": profile_ids,
                    "link_ids": [link_id, previous_link_id],
                    "managed_transcript_ids": [resolved.managed_transcript_id],
                    "scopes": scopes,
                },
            )
            return MutationResult(
                outcome=outcome,
                profile_id=profile_id,
                link_id=link_id,
                event_ids=(event_id,),
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles", "speaker_links"),
                    profile_ids=tuple(profile_ids),
                    link_ids=(link_id, previous_link_id),
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
        clear_notes: bool = False,
        accent_color: str | None = None,
        clear_accent: bool = False,
        actor: str = "user",
    ) -> MutationResult:
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)

            self._assert_entities_readable(profile_ids=(profile_id,))

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
            updated = apply_profile_update(
                current,
                display_name=display_name,
                aliases=aliases,
                notes=notes,
                clear_notes=clear_notes,
                accent_color=accent_color,
                clear_accent=clear_accent,
            ).model_copy(update={"updated_at": now})
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
            scopes = ["speaker_profiles"]
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
                    "profile_ids": [profile_id],
                    "link_ids": [],
                    "managed_transcript_ids": [],
                    "scopes": scopes,
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

            self._assert_entities_readable(profile_ids=(profile_id,))

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
            scopes = ["speaker_profiles"]
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
                receipt_extra={
                    "profile_id": profile_id,
                    "event_ids": [event_id],
                    "profile_ids": [profile_id],
                    "link_ids": [],
                    "managed_transcript_ids": [],
                    "scopes": scopes,
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

    def unarchive_profile(
        self,
        *,
        operation_idempotency_key: str,
        profile_id: str,
        expected_content_sha256: str,
        actor: str = "user",
    ) -> MutationResult:
        """Restore an archived profile to active status."""
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)

            self._assert_entities_readable(profile_ids=(profile_id,))

            current = read_profile(profile_id, root=self.root)
            if current is None:
                raise SpeakerProfileContractError(f"profile not found: {profile_id}")
            if current.status == "merged":
                raise SpeakerProfileContractError("cannot unarchive a merged profile")
            if current.status == "active":
                raise SpeakerProfileContractError("profile is already active")
            if current.status != "archived":
                raise SpeakerProfileContractError(
                    f"cannot unarchive profile in status {current.status!r}"
                )
            actual = profile_content_sha256(profile_id, root=self.root)
            if actual != expected_content_sha256:
                raise StaleUpdateError(
                    f"profile {profile_id} stale: expected {expected_content_sha256}, "
                    f"found {actual}"
                )
            now = utc_now_iso()
            updated = current.model_copy(
                update={"status": "active", "updated_at": now}
            )
            event_id = str(uuid4())
            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="profile_unarchived",
                created_at=now,
                actor=actor,
                payload={"profile_id": profile_id},
            )
            scopes = ["speaker_profiles"]
            outcome = self.engine.run(
                op_type="unarchive_profile",
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
                    "profile_ids": [profile_id],
                    "link_ids": [],
                    "managed_transcript_ids": [],
                    "scopes": scopes,
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

            self._assert_entities_readable(
                profile_ids=(source_profile_id, target_profile_id)
            )

            source = read_profile(source_profile_id, root=self.root)
            target = read_profile(target_profile_id, root=self.root)
            if source is None or target is None:
                raise SpeakerProfileContractError("source or target profile missing")
            if target.status != "active":
                raise SpeakerProfileContractError(
                    f"merge target must be active, got {target.status!r}"
                )
            if source.status == "merged":
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
            from transcriptx.core.speaker_profiles.identity import link_file_key as lfk

            links = list_profile_links(source_profile_id, root=self.root)
            link_keys = [
                lfk(lnk.managed_transcript_id, lnk.local_speaker_key) for lnk in links
            ]
            if link_keys:
                self._assert_entities_readable(link_file_keys=link_keys)

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
            for lnk, key in zip(links, link_keys, strict=True):
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
            link_ids = [lnk.link_id for lnk in links]
            managed_ids = list(
                dict.fromkeys(lnk.managed_transcript_id for lnk in links)
            )
            scopes = ["speaker_profiles", "speaker_links"]
            outcome = self.engine.run(
                op_type="merge_profiles",
                operation_idempotency_key=operation_idempotency_key,
                writes=writes,
                deletes=[],
                receipt_extra={
                    "profile_id": source_profile_id,
                    "target_profile_id": target_profile_id,
                    "event_ids": [event_id],
                    "profile_ids": [source_profile_id, target_profile_id],
                    "link_ids": link_ids,
                    "managed_transcript_ids": managed_ids,
                    "scopes": scopes,
                },
            )
            return MutationResult(
                outcome=outcome,
                profile_id=source_profile_id,
                event_ids=(event_id,),
                cache_signal=CacheInvalidationSignal(
                    scopes=("speaker_profiles", "speaker_links"),
                    profile_ids=(source_profile_id, target_profile_id),
                    link_ids=tuple(link_ids),
                    managed_transcript_ids=tuple(managed_ids),
                ),
            )

    def supersede_link_fingerprint(
        self,
        *,
        operation_idempotency_key: str,
        managed_transcript_id: str,
        local_speaker_key: str,
        expected_link_id: str | None = None,
        expected_fingerprint: str | None = None,
        expected_link_sha256: str | None = None,
        actor: str = "user",
    ) -> MutationResult:
        """Journalled fingerprint supersession after needs_review mismatch."""
        ensure_layout(self.root)
        with self._project_lock():
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self._result_from_receipt(replay)

            resolved = self.resolver.resolve(managed_transcript_id)
            key = link_file_key(resolved.managed_transcript_id, local_speaker_key)
            self._assert_entities_readable(link_file_keys=(key,))

            existing = read_live_link(key, root=self.root)
            if existing is None:
                raise SpeakerProfileContractError("no live link to supersede")

            self._assert_entities_readable(
                profile_ids=(existing.profile_id,),
                link_file_keys=(key,),
            )

            occurrences = discover_occurrences_for_resolved(resolved)
            occ = self._require_occurrence(occurrences, local_speaker_key)
            assert_occurrence_linkable(occ)
            self._reject_if_ignored(resolved.transcript_path, local_speaker_key)

            self._assert_expected_link(
                existing,
                link_file_key_value=key,
                expected_link_id=expected_link_id,
                expected_link_sha256=expected_link_sha256,
                expected_fingerprint=expected_fingerprint,
            )

            if occ.occurrence_fingerprint == existing.occurrence_fingerprint:
                return _noop_result(
                    "supersede_link_fingerprint",
                    operation_idempotency_key,
                    profile_id=existing.profile_id,
                    link_id=existing.link_id,
                    profile_ids=[existing.profile_id],
                    link_ids=[existing.link_id],
                    managed_transcript_ids=[existing.managed_transcript_id],
                    link_file_key=key,
                )

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
            scopes = ["speaker_profiles", "speaker_links"]
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
                    "profile_ids": [existing.profile_id],
                    "link_ids": [existing.link_id],
                    "managed_transcript_ids": [existing.managed_transcript_id],
                    "scopes": scopes,
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
            self._assert_entities_readable(link_file_keys=(key,))

            existing = read_live_link(key, root=self.root)
            if existing is None:
                raise SpeakerProfileContractError("no live link to migrate")

            self._assert_entities_readable(
                profile_ids=(existing.profile_id,),
                link_file_keys=(key,),
            )

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
            scopes = ["speaker_profiles", "speaker_links"]
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
                    "link_file_key": key,
                    "profile_ids": [existing.profile_id],
                    "link_ids": [existing.link_id],
                    "managed_transcript_ids": [existing.managed_transcript_id],
                    "scopes": scopes,
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

    def _result_from_receipt(self, outcome: OperationOutcome) -> MutationResult:
        receipt = outcome.receipt
        profile_ids_raw = receipt.get("profile_ids")
        if isinstance(profile_ids_raw, list):
            profile_ids = tuple(str(x) for x in profile_ids_raw)
        else:
            scalar = receipt.get("profile_id")
            profile_ids = (str(scalar),) if scalar else ()

        link_ids_raw = receipt.get("link_ids")
        if isinstance(link_ids_raw, list):
            link_ids = tuple(str(x) for x in link_ids_raw)
        else:
            scalar_link = receipt.get("link_id")
            link_ids = (str(scalar_link),) if scalar_link else ()

        managed_raw = receipt.get("managed_transcript_ids") or ()
        managed_transcript_ids = tuple(str(x) for x in managed_raw)

        scopes_raw = receipt.get("scopes")
        scopes: list[str] = []
        if isinstance(scopes_raw, list) and scopes_raw:
            scopes = [str(s) for s in scopes_raw]
        if "speaker_profiles" not in scopes:
            scopes.insert(0, "speaker_profiles")
        if (
            link_ids or receipt.get("link_file_key") or receipt.get("link_id")
        ) and "speaker_links" not in scopes:
            scopes.append("speaker_links")

        profile_id = receipt.get("profile_id") or (
            profile_ids[0] if profile_ids else None
        )
        link_id = receipt.get("link_id") or (link_ids[0] if link_ids else None)
        event_ids = tuple(receipt.get("event_ids") or ())
        return MutationResult(
            outcome=outcome,
            profile_id=profile_id,
            link_id=link_id,
            event_ids=event_ids,
            cache_signal=CacheInvalidationSignal(
                scopes=tuple(scopes),  # type: ignore[arg-type]
                profile_ids=profile_ids,
                link_ids=link_ids,
                managed_transcript_ids=managed_transcript_ids,
            ),
        )

    def _assert_expected_link(
        self,
        existing: SpeakerProfileLinkV1,
        *,
        link_file_key_value: str,
        expected_link_id: str | None = None,
        expected_link_sha256: str | None = None,
        expected_owner_profile_id: str | None = None,
        expected_fingerprint: str | None = None,
    ) -> None:
        if expected_link_id is not None and existing.link_id != expected_link_id:
            raise StaleConfirmationError(
                f"link_id mismatch: expected {expected_link_id}, "
                f"found {existing.link_id}"
            )
        if (
            expected_owner_profile_id is not None
            and existing.profile_id != expected_owner_profile_id
        ):
            raise StaleConfirmationError(
                f"owner profile_id mismatch: expected {expected_owner_profile_id}, "
                f"found {existing.profile_id}"
            )
        if (
            expected_fingerprint is not None
            and existing.occurrence_fingerprint != expected_fingerprint
        ):
            raise StaleConfirmationError(
                f"fingerprint mismatch: expected {expected_fingerprint}, "
                f"found {existing.occurrence_fingerprint}"
            )
        if expected_link_sha256 is not None:
            actual = sha256_file(link_path(link_file_key_value, root=self.root))
            if actual != expected_link_sha256:
                raise StaleConfirmationError(
                    f"link content sha256 mismatch: expected {expected_link_sha256}, "
                    f"found {actual}"
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
