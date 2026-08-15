"""Watcher pipeline: stabilize → classify → import or queue transcription."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from transcriptx.core.utils.logger import get_logger
from transcriptx.io.admit_and_register import AdmitOutcomeKind
from transcriptx.io.folder_import import (
    ELIGIBLE_STATUSES,
    admit_inbox_candidate,
    classify_inbox_file,
)
from transcriptx.io.import_admission import is_under_directory, resolve_transcripts_root
from transcriptx.services.watcher.classifier import WatchKind, classify_path
from transcriptx.services.watcher.job_store import JobState, JobStore, WatcherJob
from transcriptx.services.watcher.settings import DirectoryWatcherSettings
from transcriptx.services.watcher.stability import wait_until_stable

logger = get_logger()

_SUCCESS_ADMIT = frozenset(
    {
        AdmitOutcomeKind.IMPORTED_AND_REGISTERED,
        AdmitOutcomeKind.PARTIAL_STATE_REPAIRED,
        AdmitOutcomeKind.REGISTRATION_RECOVERED,
        AdmitOutcomeKind.ALREADY_MANAGED,
        AdmitOutcomeKind.REGISTRATION_FAILED_AFTER_ARTIFACT_COMMIT,
    }
)


def process_watched_path(
    path: Path | str,
    *,
    settings: DirectoryWatcherSettings,
    store: JobStore,
    cancel_check: Callable[[], bool] | None = None,
) -> WatcherJob:
    """Run the full per-file pipeline; returns the final job record."""
    target = Path(path)
    job = store.create(
        path=str(target),
        basename=target.name,
        state=JobState.DETECTED,
    )

    def _cancelled() -> bool:
        return bool(cancel_check and cancel_check())

    if _cancelled():
        return store.update(job, state=JobState.CANCELLED, detail="Watcher stopped.")

    transcripts_root = resolve_transcripts_root()
    try:
        if is_under_directory(target.resolve(strict=False), transcripts_root):
            return store.update(
                job,
                state=JobState.SKIPPED,
                detail="Path is under managed transcripts library.",
            )
    except OSError:
        pass

    store.update(job, state=JobState.STABILIZING, detail="Waiting for file to settle.")
    if _cancelled():
        return store.update(job, state=JobState.CANCELLED, detail="Watcher stopped.")

    identity = wait_until_stable(
        target,
        checks=settings.stability_checks,
        interval_ms=settings.stability_interval_ms,
        timeout_ms=max(settings.debounce_ms * 4, 30_000),
    )
    if identity is None:
        return store.update(
            job,
            state=JobState.FAILED,
            detail="File did not stabilize (still growing, missing, or not a regular file).",
        )

    store.update(
        job,
        identity={
            "st_dev": identity.st_dev,
            "st_ino": identity.st_ino,
            "size": identity.size,
            "mtime_ns": identity.mtime_ns,
        },
    )

    kind = classify_path(target, settings)
    store.update(job, state=JobState.CLASSIFIED, kind=kind.value)

    if kind is WatchKind.IGNORE:
        return store.update(job, state=JobState.SKIPPED, detail="Extension ignored.")

    if kind is WatchKind.AUDIO:
        if settings.audio_mode == "ignore":
            return store.update(
                job, state=JobState.SKIPPED, detail="Audio mode is ignore."
            )
        if settings.audio_mode == "auto_transcribe":
            return store.update(
                job,
                state=JobState.FAILED,
                detail=(
                    "auto_transcribe is not available until a host STT provider "
                    "is configured (theme H)."
                ),
            )
        # offer
        return store.update(
            job,
            state=JobState.QUEUED_TRANSCRIPTION,
            detail="Audio queued for transcription (offer mode).",
        )

    # Transcript path
    if settings.transcript_mode == "ignore":
        return store.update(
            job, state=JobState.SKIPPED, detail="Transcript mode is ignore."
        )
    if settings.transcript_mode == "offer":
        return store.update(
            job,
            state=JobState.SKIPPED,
            detail="Transcript detected (offer mode — not auto-imported).",
            kind=kind.value,
        )

    # auto_import
    if _cancelled():
        return store.update(job, state=JobState.CANCELLED, detail="Watcher stopped.")

    store.update(
        job, state=JobState.IMPORTING, detail="Admitting into managed library."
    )
    candidate = classify_inbox_file(
        target,
        expected_dev=identity.st_dev,
        expected_ino=identity.st_ino,
        expected_size=identity.size,
        expected_mtime_ns=identity.mtime_ns,
    )
    if candidate.status not in ELIGIBLE_STATUSES:
        return store.update(
            job,
            state=JobState.SKIPPED,
            detail=f"{candidate.status.value}: {candidate.secondary_detail}".strip(
                ": "
            ),
        )

    outcome = admit_inbox_candidate(candidate)
    if outcome.kind in _SUCCESS_ADMIT:
        return store.update(
            job,
            state=JobState.IMPORTED,
            detail=outcome.user_safe_detail,
            transcript_path=(
                str(outcome.transcript_path) if outcome.transcript_path else None
            ),
            slug=outcome.slug,
        )
    return store.update(
        job,
        state=JobState.FAILED,
        detail=outcome.user_safe_detail,
    )
