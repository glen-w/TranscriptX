"""Background / blocking runner for the transcription workflow."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Optional

from transcriptx.app.controllers.transcription_controller import TranscriptionController
from transcriptx.app.models.errors import TranscriptionCancelled, WorkflowExecutionError
from transcriptx.app.models.requests import (
    TranscriptionConversionOptions,
    TranscriptionOptions,
    TranscriptionRequest,
)
from transcriptx.app.models.results import TranscriptionBatchResult
from transcriptx.app.progress import ProgressCallback, ProgressEvent
from transcriptx.core.audio.types import SUPPORTED_AUDIO_EXTENSIONS
from transcriptx.core.utils.logger import get_logger
from transcriptx.services.transcription.env import (
    default_conversion_options,
    default_transcription_options,
)
from transcriptx.services.transcription.job_store import (
    TranscriptionJob,
    TranscriptionJobState,
    TranscriptionJobStore,
)
from transcriptx.services.transcription.registry import (
    any_provider_available,
    resolve_default_provider,
)

logger = get_logger()

_RUNNER_LOCK = threading.RLock()
_RUNNER: TranscriptionJobRunner | None = None


def collect_audio_input_paths(raw: str | Path) -> list[Path]:
    """Resolve a file or folder into existing supported audio paths."""
    path = Path(str(raw)).expanduser()
    if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS:
        return [path.resolve()]
    if not path.is_dir():
        return []
    found: set[Path] = set()
    for child in path.iterdir():
        if child.is_file() and child.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS:
            found.add(child.resolve())
    return sorted(found)


class JobStoreProgress:
    """ProgressCallback that persists into TranscriptionJobStore."""

    def __init__(self, store: TranscriptionJobStore, job_id: str) -> None:
        self._store = store
        self._job_id = job_id

    def _job(self) -> TranscriptionJob | None:
        return self._store.get(self._job_id)

    def on_stage_start(self, stage_name: str) -> None:
        job = self._job()
        if job is not None:
            self._store.append_log(job, f"stage: {stage_name}")

    def on_stage_progress(
        self,
        message: str,
        pct: Optional[float] = None,
        *,
        current_item: Optional[str] = None,
    ) -> None:
        job = self._job()
        if job is None:
            return
        extra = f" ({current_item})" if current_item else ""
        self._store.update(
            job,
            progress_message=f"{message}{extra}",
            progress_pct=pct,
        )
        self._store.append_log(self._job() or job, message)

    def on_stage_complete(self, stage_name: str) -> None:
        job = self._job()
        if job is not None:
            self._store.append_log(job, f"done: {stage_name}")

    def on_log(self, message: str, level: str = "info") -> None:
        _ = level
        job = self._job()
        if job is not None:
            self._store.append_log(job, message)

    def on_event(self, event: ProgressEvent) -> None:
        job = self._job()
        if job is None:
            return
        if isinstance(event, dict):
            msg = str(event.get("message") or event.get("event") or "")
            if msg:
                self._store.append_log(job, msg)


def _options_for_run(
    options: TranscriptionOptions | None = None,
) -> TranscriptionOptions:
    base = options or default_transcription_options()
    provider = resolve_default_provider(base)
    if provider.provider_id == base.provider_id:
        return base
    return TranscriptionOptions(
        provider_id=provider.provider_id,
        model=base.model,
        language=base.language,
        diarize=base.diarize,
        timeout_seconds=base.timeout_seconds,
        device=base.device,
        compute_type=base.compute_type,
        batch_size=base.batch_size,
        min_speakers=base.min_speakers,
        max_speakers=base.max_speakers,
        docker_image=base.docker_image,
    )


class TranscriptionJobRunner:
    """Process-level job executor: file-backed jobs + daemon worker threads."""

    def __init__(self, store: TranscriptionJobStore | None = None) -> None:
        self._store = store or TranscriptionJobStore()
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}

    @property
    def store(self) -> TranscriptionJobStore:
        return self._store

    def submit(
        self,
        request: TranscriptionRequest,
        *,
        watcher_job_id: str | None = None,
    ) -> TranscriptionJob:
        opts = request.transcription_options
        job = self._store.create(
            provider_id=opts.provider_id,
            input_paths=[str(p) for p in request.input_paths],
            model=opts.model,
            language=opts.language,
            diarize=opts.diarize,
            import_into_library=request.import_into_library,
            output_dir=str(request.output_dir) if request.output_dir else None,
            watcher_job_id=watcher_job_id,
        )
        request.job_id = job.job_id
        thread = threading.Thread(
            target=self._execute,
            args=(job.job_id, request),
            name=f"transcriptx-stt-{job.job_id}",
            daemon=True,
        )
        with self._lock:
            self._threads[job.job_id] = thread
        thread.start()
        return job

    def run_blocking(
        self,
        request: TranscriptionRequest,
        *,
        cancel_check: Callable[[], bool] | None = None,
        watcher_job_id: str | None = None,
    ) -> TranscriptionBatchResult:
        opts = request.transcription_options
        job = self._store.create(
            provider_id=opts.provider_id,
            input_paths=[str(p) for p in request.input_paths],
            model=opts.model,
            language=opts.language,
            diarize=opts.diarize,
            import_into_library=request.import_into_library,
            output_dir=str(request.output_dir) if request.output_dir else None,
            watcher_job_id=watcher_job_id,
            job_id=request.job_id,
        )
        request.job_id = job.job_id
        return self._execute(job.job_id, request, extra_cancel=cancel_check)

    def request_cancel(self, job_id: str) -> TranscriptionJob | None:
        return self._store.request_cancel(job_id)

    def _cancel_flag(
        self, job_id: str, extra: Callable[[], bool] | None
    ) -> Callable[[], bool]:
        def _check() -> bool:
            if extra and extra():
                return True
            job = self._store.get(job_id)
            return bool(job and job.cancel_requested)

        return _check

    def _execute(
        self,
        job_id: str,
        request: TranscriptionRequest,
        extra_cancel: Callable[[], bool] | None = None,
    ) -> TranscriptionBatchResult:
        job = self._store.get(job_id)
        if job is None:
            raise WorkflowExecutionError(f"Unknown transcription job {job_id}")
        self._store.update(job, state=TranscriptionJobState.RUNNING)
        self._sync_watcher(job, state="transcribing", detail="Transcribing…")
        progress: ProgressCallback = JobStoreProgress(self._store, job_id)
        empty = TranscriptionBatchResult(
            job_id=job_id,
            success=False,
            file_results=[],
            succeeded_count=0,
            failed_count=0,
            output_dir=request.output_dir or Path("."),
            errors=["No result"],
        )
        try:
            result = TranscriptionController().run_transcription(
                request,
                progress,
                cancel_check=self._cancel_flag(job_id, extra_cancel),
            )
        except TranscriptionCancelled:
            job = self._store.get(job_id) or job
            self._store.update(
                job,
                state=TranscriptionJobState.CANCELLED,
                progress_message="Cancelled",
            )
            self._sync_watcher(
                job, state="cancelled", detail="Transcription cancelled."
            )
            empty.errors = ["Cancelled"]
            return empty
        except Exception as exc:
            logger.exception("Transcription job %s failed", job_id)
            job = self._store.get(job_id) or job
            self._store.update(
                job,
                state=TranscriptionJobState.FAILED,
                errors=[str(exc)],
                progress_message=str(exc),
            )
            self._sync_watcher(job, state="failed", detail=str(exc))
            empty.errors = [str(exc)]
            return empty
        finally:
            with self._lock:
                self._threads.pop(job_id, None)

        job = self._store.get(job_id) or job
        imported = [
            str(fr.imported_json_path)
            for fr in result.file_results
            if fr.imported_json_path is not None
        ]
        errors = list(result.errors)
        for fr in result.file_results:
            errors.extend(fr.errors)
        state = (
            TranscriptionJobState.SUCCEEDED
            if result.success
            else TranscriptionJobState.FAILED
        )
        self._store.update(
            job,
            state=state,
            succeeded_count=result.succeeded_count,
            failed_count=result.failed_count,
            imported_paths=imported,
            errors=errors,
            duration_seconds=result.duration_seconds,
            progress_pct=100.0 if result.success else job.progress_pct,
            progress_message=(
                f"Finished ({result.succeeded_count} ok, {result.failed_count} failed)"
            ),
        )
        if result.success:
            detail = "Imported after transcription." if imported else "Transcribed."
            self._sync_watcher(
                job,
                state="imported",
                detail=detail,
                transcript_path=imported[0] if imported else None,
            )
        else:
            self._sync_watcher(
                job,
                state="failed",
                detail=errors[0] if errors else "Transcription failed.",
            )
        return result

    def _sync_watcher(
        self,
        job: TranscriptionJob,
        *,
        state: str,
        detail: str,
        transcript_path: str | None = None,
    ) -> None:
        if not job.watcher_job_id:
            return
        try:
            from transcriptx.services.watcher.job_store import JobState, JobStore
            from transcriptx.services.watcher.service import get_watcher_service

            watcher_job = get_watcher_service().store.get(job.watcher_job_id)
            if watcher_job is None:
                return
            mapping = {
                "transcribing": JobState.TRANSCRIBING,
                "imported": JobState.IMPORTED,
                "failed": JobState.FAILED,
                "cancelled": JobState.CANCELLED,
            }
            mapped = mapping.get(state)
            if mapped is None:
                return
            get_watcher_service().store.update(
                watcher_job,
                state=mapped,
                detail=detail,
                transcript_path=transcript_path,
            )
        except Exception:
            logger.exception("Failed to sync watcher job %s", job.watcher_job_id)


def get_transcription_runner() -> TranscriptionJobRunner:
    global _RUNNER
    with _RUNNER_LOCK:
        if _RUNNER is None:
            _RUNNER = TranscriptionJobRunner()
        return _RUNNER


def reset_transcription_runner_for_tests(
    store: TranscriptionJobStore | None = None,
) -> TranscriptionJobRunner:
    global _RUNNER
    with _RUNNER_LOCK:
        _RUNNER = TranscriptionJobRunner(store=store)
        return _RUNNER


def build_transcription_request(
    input_paths: Sequence[Path],
    *,
    options: TranscriptionOptions | None = None,
    conversion: TranscriptionConversionOptions | None = None,
    import_into_library: bool = True,
    overwrite_import: bool = False,
) -> TranscriptionRequest:
    opts = _options_for_run(options)
    return TranscriptionRequest(
        input_paths=list(input_paths),
        transcription_options=opts,
        conversion_options=conversion or default_conversion_options(),
        import_into_library=import_into_library,
        overwrite_import=overwrite_import,
    )


def drain_queued_watcher_jobs(*, limit: int = 20) -> int:
    """Submit STT jobs for watcher rows still in queued_transcription."""
    if not any_provider_available():
        return 0
    from transcriptx.services.watcher.job_store import JobState
    from transcriptx.services.watcher.service import get_watcher_service

    service = get_watcher_service()
    runner = get_transcription_runner()
    submitted = 0
    for watcher_job in service.store.list_jobs(limit=200):
        if watcher_job.state is not JobState.QUEUED_TRANSCRIPTION:
            continue
        path = Path(watcher_job.path)
        if not path.is_file():
            service.store.update(
                watcher_job,
                state=JobState.FAILED,
                detail="Queued audio is missing.",
            )
            continue
        request = build_transcription_request([path], import_into_library=True)
        service.store.update(
            watcher_job,
            state=JobState.TRANSCRIBING,
            detail="Submitting in-app transcription.",
        )
        runner.submit(request, watcher_job_id=watcher_job.job_id)
        submitted += 1
        if submitted >= limit:
            break
    return submitted


def transcribe_audio_path_blocking(
    path: Path,
    *,
    cancel_check: Callable[[], bool] | None = None,
    watcher_job_id: str | None = None,
    options: TranscriptionOptions | None = None,
) -> TranscriptionBatchResult:
    """Used by the directory watcher auto_transcribe path."""
    request = build_transcription_request(
        [path], options=options, import_into_library=True
    )
    return get_transcription_runner().run_blocking(
        request, cancel_check=cancel_check, watcher_job_id=watcher_job_id
    )
