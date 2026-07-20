"""Admit transcript artifacts and register them under one per-target lock."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
from transcriptx.core.utils.slug_manager import (
    get_registered_slug_for_path_and_identity,
    register_transcript,
    registration_is_valid,
)
from transcriptx.core.utils._path_core import get_canonical_base_name
from transcriptx.io.import_admission import (
    AdmissionError,
    ManagedArtifactState,
    assert_within_import_size_limit,
    derive_canonical_target,
    inspect_managed_artifact_state,
    sanitize_upload_basename,
)
from transcriptx.io.import_core.errors import ImportErrorBase
from transcriptx.io.import_metadata_sidecar import validate_managed_transcript
from transcriptx.io.managed_import_workflow import (
    StagingCleanupPolicy,
    run_managed_import_workflow,
)

logger = get_logger()


class AdmitOutcomeKind(str, Enum):
    IMPORTED_AND_REGISTERED = "imported_and_registered"
    PARTIAL_STATE_REPAIRED = "partial_state_repaired"
    REGISTRATION_RECOVERED = "registration_recovered"
    REGISTRATION_FAILED_AFTER_ARTIFACT_COMMIT = (
        "registration_failed_after_artifact_commit"
    )
    ALREADY_MANAGED = "already_managed"
    CONCURRENT_SKIP = "concurrent_skip"
    STALE_CANDIDATE = "stale_candidate"
    INCOMPLETE_STATE_FAILURE = "incomplete_state_failure"
    UNSUPPORTED_OR_INVALID_INPUT = "unsupported_or_invalid_input"
    UNEXPECTED_FAILURE = "unexpected_failure"


@dataclass(frozen=True)
class AdmitOutcome:
    kind: AdmitOutcomeKind
    transcript_path: Path | None
    slug: str | None
    artifact_committed: bool
    registration_progressed: bool
    user_safe_detail: str


def _load_segments(transcript_path: Path) -> list[Any]:
    with open(transcript_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    segments = data.get("segments") if isinstance(data, dict) else None
    if not segments or not isinstance(segments, list):
        raise ValueError("No segments found in transcript")
    return segments


def _identity_for(transcript_path: Path) -> str:
    return compute_transcript_identity_hash(_load_segments(transcript_path))


def _try_register(transcript_path: Path) -> str:
    validation = validate_managed_transcript(transcript_path)
    if not validation.ok:
        raise ValueError(
            f"Transcript is not library-valid managed transcript: {validation.message}"
        )
    identity = _identity_for(transcript_path)
    source_basename = get_canonical_base_name(str(transcript_path))
    return register_transcript(
        transcript_key=identity,
        transcript_path=str(transcript_path),
        run_id=None,
        source_basename=source_basename,
        source_path=str(transcript_path),
    )


def _outcome_after_reinspect(
    *,
    target_json: Path,
    transcripts_dir: Path,
) -> AdmitOutcome | None:
    """After FileExistsError / state change, choose skip vs registration recovery."""
    inspection = inspect_managed_artifact_state(
        target_json, transcripts_dir=transcripts_dir
    )
    if inspection.state is ManagedArtifactState.ALREADY_MANAGED:
        try:
            identity = _identity_for(target_json)
        except Exception as exc:
            return AdmitOutcome(
                kind=AdmitOutcomeKind.INCOMPLETE_STATE_FAILURE,
                transcript_path=target_json,
                slug=None,
                artifact_committed=True,
                registration_progressed=False,
                user_safe_detail=f"Managed artifact is not readable for registration: {exc}",
            )
        if registration_is_valid(target_json, identity):
            slug = get_registered_slug_for_path_and_identity(target_json, identity)
            return AdmitOutcome(
                kind=AdmitOutcomeKind.CONCURRENT_SKIP,
                transcript_path=target_json,
                slug=slug,
                artifact_committed=True,
                registration_progressed=False,
                user_safe_detail="Transcript was already managed by another import.",
            )
        try:
            slug = _try_register(target_json)
        except Exception as exc:
            return AdmitOutcome(
                kind=AdmitOutcomeKind.REGISTRATION_FAILED_AFTER_ARTIFACT_COMMIT,
                transcript_path=target_json,
                slug=None,
                artifact_committed=True,
                registration_progressed=False,
                user_safe_detail=f"Managed artifact exists but registration failed: {exc}",
            )
        return AdmitOutcome(
            kind=AdmitOutcomeKind.REGISTRATION_RECOVERED,
            transcript_path=target_json,
            slug=slug,
            artifact_committed=True,
            registration_progressed=True,
            user_safe_detail="Recovered missing registration for an existing managed transcript.",
        )
    if inspection.state in {
        ManagedArtifactState.INCOMPLETE_REPAIRABLE,
        ManagedArtifactState.INCOMPLETE_UNREPAIRABLE,
        ManagedArtifactState.INCONSISTENT,
    }:
        return AdmitOutcome(
            kind=AdmitOutcomeKind.INCOMPLETE_STATE_FAILURE,
            transcript_path=target_json,
            slug=None,
            artifact_committed=False,
            registration_progressed=False,
            user_safe_detail=inspection.detail
            or "Managed transcript is in an incomplete or inconsistent state.",
        )
    return None


def admit_and_register(
    source_path: str | Path,
    *,
    logical_basename: str | None = None,
    staging_cleanup: StagingCleanupPolicy = StagingCleanupPolicy.NEVER,
    allow_provenance_backfill: bool = False,
    expected_size: int | None = None,
) -> AdmitOutcome:
    """Inspect, admit (or repair), and register under one per-target lock.

    Holds the target JSON :class:`FileLock` across managed write and registration
    so concurrent callers cannot race registration after artifact commit.
    """
    staging = Path(source_path)
    try:
        if not staging.is_file():
            return AdmitOutcome(
                kind=AdmitOutcomeKind.UNSUPPORTED_OR_INVALID_INPUT,
                transcript_path=None,
                slug=None,
                artifact_committed=False,
                registration_progressed=False,
                user_safe_detail="Source file is missing or not a regular file.",
            )
        size = staging.stat().st_size if expected_size is None else expected_size
        assert_within_import_size_limit(size)
        basename = sanitize_upload_basename(
            logical_basename if logical_basename is not None else staging.name
        )
        target = derive_canonical_target(basename)
    except AdmissionError as exc:
        return AdmitOutcome(
            kind=AdmitOutcomeKind.UNSUPPORTED_OR_INVALID_INPUT,
            transcript_path=None,
            slug=None,
            artifact_committed=False,
            registration_progressed=False,
            user_safe_detail=str(exc),
        )
    except OSError as exc:
        return AdmitOutcome(
            kind=AdmitOutcomeKind.UNSUPPORTED_OR_INVALID_INPUT,
            transcript_path=None,
            slug=None,
            artifact_committed=False,
            registration_progressed=False,
            user_safe_detail=f"Could not read source file: {exc}",
        )

    transcripts_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    target_json = target.target_json

    try:
        with FileLock(target_json, timeout=30) as lock:
            if not lock.acquired:
                return AdmitOutcome(
                    kind=AdmitOutcomeKind.UNEXPECTED_FAILURE,
                    transcript_path=None,
                    slug=None,
                    artifact_committed=False,
                    registration_progressed=False,
                    user_safe_detail=f"Could not acquire import lock for {target_json.name}.",
                )

            inspection = inspect_managed_artifact_state(
                target_json, transcripts_dir=transcripts_dir
            )

            if inspection.state is ManagedArtifactState.ALREADY_MANAGED:
                recovered = _outcome_after_reinspect(
                    target_json=target_json, transcripts_dir=transcripts_dir
                )
                if recovered is not None:
                    if recovered.kind is AdmitOutcomeKind.CONCURRENT_SKIP:
                        # Fully managed + registered → already_managed for deliberate admit.
                        return AdmitOutcome(
                            kind=AdmitOutcomeKind.ALREADY_MANAGED,
                            transcript_path=recovered.transcript_path,
                            slug=recovered.slug,
                            artifact_committed=True,
                            registration_progressed=False,
                            user_safe_detail="Transcript is already managed and registered.",
                        )
                    return recovered

            if inspection.state is ManagedArtifactState.INCONSISTENT:
                return AdmitOutcome(
                    kind=AdmitOutcomeKind.INCOMPLETE_STATE_FAILURE,
                    transcript_path=target_json,
                    slug=None,
                    artifact_committed=False,
                    registration_progressed=False,
                    user_safe_detail=inspection.detail
                    or "Import sidecar exists without canonical JSON.",
                )

            if (
                inspection.state is ManagedArtifactState.INCOMPLETE_UNREPAIRABLE
                and not allow_provenance_backfill
            ):
                return AdmitOutcome(
                    kind=AdmitOutcomeKind.INCOMPLETE_STATE_FAILURE,
                    transcript_path=target_json,
                    slug=None,
                    artifact_committed=False,
                    registration_progressed=False,
                    user_safe_detail=inspection.detail
                    or "Incomplete managed transcript cannot be repaired safely.",
                )

            try:
                managed = run_managed_import_workflow(
                    staging,
                    logical_upload_basename=basename,
                    overwrite=False,
                    staging_cleanup=staging_cleanup,
                    allow_provenance_backfill=allow_provenance_backfill,
                    acquire_lock=False,
                )
            except FileExistsError:
                reinspect = _outcome_after_reinspect(
                    target_json=target_json, transcripts_dir=transcripts_dir
                )
                if reinspect is not None:
                    return reinspect
                return AdmitOutcome(
                    kind=AdmitOutcomeKind.CONCURRENT_SKIP,
                    transcript_path=target_json,
                    slug=None,
                    artifact_committed=True,
                    registration_progressed=False,
                    user_safe_detail="Transcript already exists.",
                )
            except (AdmissionError, ImportErrorBase) as exc:
                return AdmitOutcome(
                    kind=AdmitOutcomeKind.UNSUPPORTED_OR_INVALID_INPUT,
                    transcript_path=None,
                    slug=None,
                    artifact_committed=False,
                    registration_progressed=False,
                    user_safe_detail=str(exc),
                )
            except ValueError as exc:
                return AdmitOutcome(
                    kind=AdmitOutcomeKind.INCOMPLETE_STATE_FAILURE,
                    transcript_path=target_json if target_json.exists() else None,
                    slug=None,
                    artifact_committed=False,
                    registration_progressed=False,
                    user_safe_detail=str(exc),
                )

            json_path = managed.json_path
            try:
                slug = _try_register(json_path)
            except Exception as exc:
                logger.exception("Registration failed after artifact commit")
                return AdmitOutcome(
                    kind=AdmitOutcomeKind.REGISTRATION_FAILED_AFTER_ARTIFACT_COMMIT,
                    transcript_path=json_path,
                    slug=None,
                    artifact_committed=True,
                    registration_progressed=False,
                    user_safe_detail=f"Import succeeded but registration failed: {exc}",
                )

            kind = (
                AdmitOutcomeKind.PARTIAL_STATE_REPAIRED
                if managed.repaired_incomplete
                else AdmitOutcomeKind.IMPORTED_AND_REGISTERED
            )
            detail = "Imported and registered transcript."
            if managed.repaired_incomplete:
                detail = "Repaired incomplete managed transcript and registered it."
            if managed.speaker_map_error:
                detail = f"{detail} Speaker map inheritance warning: {managed.speaker_map_error}"
            return AdmitOutcome(
                kind=kind,
                transcript_path=json_path,
                slug=slug,
                artifact_committed=True,
                registration_progressed=True,
                user_safe_detail=detail,
            )
    except Exception as exc:
        logger.exception("Unexpected admit_and_register failure")
        return AdmitOutcome(
            kind=AdmitOutcomeKind.UNEXPECTED_FAILURE,
            transcript_path=None,
            slug=None,
            artifact_committed=False,
            registration_progressed=False,
            user_safe_detail=f"Unexpected import failure: {exc}",
        )
