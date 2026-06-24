"""
Transcription workflow — no Streamlit or presentation-layer concerns.

Per-file phases: validating → converting → transcribing → importing → finalizing
Batch: sequential processing with continue-on-error.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from transcriptx.app.models.requests import TranscriptionRequest
from transcriptx.app.models.results import (
    TranscriptionBatchResult,
    TranscriptionFileResult,
)
from transcriptx.app.progress import NullProgress, ProgressCallback
from transcriptx.core.audio.conversion import export_mp3_for_transcription
from transcriptx.core.audio.types import SUPPORTED_AUDIO_EXTENSIONS
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import PATHS
from transcriptx.io.managed_import_workflow import run_managed_import_workflow
from transcriptx.services.transcription.env import get_secret, load_merged_env
from transcriptx.services.transcription.redact import redact_secret
from transcriptx.services.transcription.registry import get_provider

logger = get_logger()


def _transcription_staging_dir(job_id: str) -> Path:
    return PATHS.data_dir / "transcription" / "staging" / job_id


def _default_output_dir(job_id: str) -> Path:
    return PATHS.data_dir / "transcription" / "output" / job_id


def _collect_secrets() -> list[str]:
    merged = load_merged_env()
    token = get_secret("HF_TOKEN", merged)
    return [token] if token else []


def run_transcription_workflow(
    request: TranscriptionRequest,
    progress: ProgressCallback | None = None,
) -> TranscriptionBatchResult:
    if progress is None:
        progress = NullProgress()

    batch_started = time.time()
    job_id = uuid.uuid4().hex[:12]
    staging_dir = _transcription_staging_dir(job_id)
    output_dir = request.output_dir or _default_output_dir(job_id)
    staging_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    provider = get_provider(request.transcription_options.provider_id)
    secrets = _collect_secrets()
    file_results: list[TranscriptionFileResult] = []
    succeeded = 0
    failed = 0
    batch_errors: list[str] = []

    total_files = len(request.input_paths)
    progress.on_stage_start("running_pipeline")

    for index, input_path in enumerate(request.input_paths):
        file_started = time.time()
        input_path = Path(input_path).resolve()
        errors: list[str] = []
        stderr_tail: tuple[str, ...] = ()
        staged_mp3: Path | None = None
        created_staged = False
        raw_json: Path | None = None
        imported_json: Path | None = None
        import_success: bool | None = None
        file_ok = False

        progress.on_stage_progress(
            f"Processing {input_path.name} ({index + 1}/{total_files})",
            pct=((index) / total_files * 100) if total_files else 0,
        )
        progress.on_event(
            {
                "event": "module_started",
                "module_name": input_path.name,
                "index": index + 1,
                "total": total_files,
            }
        )
        snap_msg = f"[{index + 1}/{total_files}] {input_path.name}"
        progress.on_log(redact_secret(snap_msg, secrets))

        # Validate extension
        if input_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            errors.append(f"Unsupported extension: {input_path.suffix}")
            failed += 1
            progress.on_event(
                {
                    "event": "module_failed",
                    "module_name": input_path.name,
                    "index": index + 1,
                    "total": total_files,
                    "completed": succeeded,
                    "failed": failed,
                    "error": errors[-1],
                }
            )
            file_results.append(
                TranscriptionFileResult(
                    input_path=input_path,
                    provider_id=provider.provider_id,
                    success=False,
                    created_staged_file=False,
                    staged_mp3_path=None,
                    raw_json_path=None,
                    imported_json_path=None,
                    import_success=None,
                    errors=tuple(errors),
                    stderr_tail=stderr_tail,
                    duration_seconds=time.time() - file_started,
                )
            )
            continue

        if not input_path.is_file():
            errors.append(f"File not found: {input_path}")
            failed += 1
            progress.on_event(
                {
                    "event": "module_failed",
                    "module_name": input_path.name,
                    "index": index + 1,
                    "total": total_files,
                    "completed": succeeded,
                    "failed": failed,
                    "error": errors[-1],
                }
            )
            file_results.append(
                TranscriptionFileResult(
                    input_path=input_path,
                    provider_id=provider.provider_id,
                    success=False,
                    created_staged_file=False,
                    staged_mp3_path=None,
                    raw_json_path=None,
                    imported_json_path=None,
                    import_success=None,
                    errors=tuple(errors),
                    stderr_tail=stderr_tail,
                    duration_seconds=time.time() - file_started,
                )
            )
            continue

        try:
            progress.on_log(redact_secret(f"  converting {input_path.name}", secrets))
            staged_target = staging_dir / f"{input_path.stem}.mp3"
            conv = request.conversion_options
            staged_mp3 = export_mp3_for_transcription(
                input_path,
                staged_target,
                codec=conv.codec,
                bitrate=conv.bitrate,
                channels=conv.channels,
                sample_rate=conv.sample_rate,
                force_reencode=conv.force_reencode,
            )
            created_staged = staged_mp3.resolve() != input_path.resolve()

            per_file_out = output_dir / input_path.stem
            per_file_out.mkdir(parents=True, exist_ok=True)

            progress.on_log(redact_secret(f"  transcribing {input_path.name}", secrets))
            provider_result = provider.transcribe(
                staged_mp3, per_file_out, request.transcription_options
            )
            stderr_tail = provider_result.stderr_tail
            if not provider_result.success or provider_result.json_path is None:
                err = provider_result.error or "Transcription failed"
                errors.append(redact_secret(err, secrets))
                failed += 1
                progress.on_event(
                    {
                        "event": "module_failed",
                        "module_name": input_path.name,
                        "index": index + 1,
                        "total": total_files,
                        "completed": succeeded,
                        "failed": failed,
                        "error": errors[-1],
                    }
                )
                file_results.append(
                    TranscriptionFileResult(
                        input_path=input_path,
                        provider_id=provider.provider_id,
                        success=False,
                        created_staged_file=created_staged,
                        staged_mp3_path=staged_mp3,
                        raw_json_path=provider_result.json_path,
                        imported_json_path=None,
                        import_success=None,
                        errors=tuple(errors),
                        stderr_tail=stderr_tail,
                        duration_seconds=time.time() - file_started,
                    )
                )
                if created_staged and not request.keep_intermediates:
                    try:
                        staged_mp3.unlink(missing_ok=True)
                    except OSError:
                        pass
                continue

            raw_json = provider_result.json_path
            file_ok = True

            if request.import_into_library:
                progress.on_log(
                    redact_secret(f"  importing {input_path.name}", secrets)
                )
                try:
                    managed = run_managed_import_workflow(
                        raw_json,
                        logical_upload_basename=f"{input_path.stem}.json",
                        overwrite=request.overwrite_import,
                        delete_staging_on_success=False,
                    )
                    imported_json = managed.json_path
                    import_success = True
                except Exception as exc:
                    import_success = False
                    file_ok = False
                    errors.append(redact_secret(f"Import failed: {exc}", secrets))

            if file_ok:
                succeeded += 1
                progress.on_event(
                    {
                        "event": "module_completed",
                        "module_name": input_path.name,
                        "index": index + 1,
                        "total": total_files,
                        "completed": succeeded,
                        "failed": failed,
                        "duration_ms": (time.time() - file_started) * 1000,
                    }
                )
            else:
                failed += 1
                progress.on_event(
                    {
                        "event": "module_failed",
                        "module_name": input_path.name,
                        "index": index + 1,
                        "total": total_files,
                        "completed": succeeded,
                        "failed": failed,
                        "error": errors[-1] if errors else "Failed",
                    }
                )

            if created_staged and not request.keep_intermediates:
                try:
                    staged_mp3.unlink(missing_ok=True)
                except OSError:
                    pass

            file_results.append(
                TranscriptionFileResult(
                    input_path=input_path,
                    provider_id=provider.provider_id,
                    success=file_ok,
                    created_staged_file=created_staged,
                    staged_mp3_path=staged_mp3 if request.keep_intermediates else None,
                    raw_json_path=raw_json,
                    imported_json_path=imported_json,
                    import_success=import_success,
                    errors=tuple(errors),
                    stderr_tail=stderr_tail,
                    duration_seconds=time.time() - file_started,
                )
            )

        except Exception as exc:
            msg = redact_secret(str(exc), secrets)
            errors.append(msg)
            failed += 1
            progress.on_event(
                {
                    "event": "module_failed",
                    "module_name": input_path.name,
                    "index": index + 1,
                    "total": total_files,
                    "completed": succeeded,
                    "failed": failed,
                    "error": msg,
                }
            )
            if created_staged and staged_mp3 and not request.keep_intermediates:
                try:
                    staged_mp3.unlink(missing_ok=True)
                except OSError:
                    pass
            file_results.append(
                TranscriptionFileResult(
                    input_path=input_path,
                    provider_id=provider.provider_id,
                    success=False,
                    created_staged_file=created_staged,
                    staged_mp3_path=staged_mp3,
                    raw_json_path=raw_json,
                    imported_json_path=imported_json,
                    import_success=import_success,
                    errors=tuple(errors),
                    stderr_tail=stderr_tail,
                    duration_seconds=time.time() - file_started,
                )
            )
            logger.exception("Transcription failed for %s", input_path)

    progress.on_stage_complete("running_pipeline")
    progress.on_event(
        {
            "event": "run_completed",
            "message": f"Transcription batch finished ({succeeded}/{total_files} succeeded)",
        }
    )
    progress.on_stage_start("completed")
    progress.on_stage_complete("completed")

    return TranscriptionBatchResult(
        job_id=job_id,
        success=failed == 0 and succeeded > 0,
        file_results=file_results,
        succeeded_count=succeeded,
        failed_count=failed,
        output_dir=output_dir,
        errors=batch_errors,
        duration_seconds=time.time() - batch_started,
    )
