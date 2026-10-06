"""Tests for transcription job runner helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.app.models.requests import (
    TranscriptionConversionOptions,
    TranscriptionOptions,
    TranscriptionRequest,
)
from transcriptx.app.models.results import TranscriptionBatchResult
from transcriptx.services.transcription.job_store import (
    TranscriptionJobState,
    TranscriptionJobStore,
)
from transcriptx.services.transcription.runner import (
    collect_audio_input_paths,
    reset_transcription_runner_for_tests,
)


@pytest.mark.unit
def test_collect_audio_input_paths_file_and_folder(tmp_path: Path) -> None:
    clip = tmp_path / "talk.mp3"
    clip.write_bytes(b"x")
    other = tmp_path / "notes.txt"
    other.write_text("nope", encoding="utf-8")
    nested = tmp_path / "nested.wav"
    nested.write_bytes(b"y")
    assert collect_audio_input_paths(clip) == [clip.resolve()]
    found = collect_audio_input_paths(tmp_path)
    assert clip.resolve() in found
    assert nested.resolve() in found
    assert all(p.suffix.lower() != ".txt" for p in found)


@pytest.mark.unit
def test_run_blocking_records_success(tmp_path: Path) -> None:
    store = TranscriptionJobStore(tmp_path / "jobs")
    runner = reset_transcription_runner_for_tests(store)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"x")
    expected = TranscriptionBatchResult(
        job_id="will-be-replaced",
        success=True,
        file_results=[],
        succeeded_count=1,
        failed_count=0,
        output_dir=tmp_path,
        duration_seconds=0.1,
    )
    request = TranscriptionRequest(
        input_paths=[audio],
        transcription_options=TranscriptionOptions(
            provider_id="whispermlx",
            model="tiny",
            language="en",
            diarize=False,
        ),
        conversion_options=TranscriptionConversionOptions(),
        import_into_library=False,
    )
    with patch(
        "transcriptx.services.transcription.runner.TranscriptionController"
    ) as ctrl_cls:
        ctrl_cls.return_value.run_transcription.return_value = expected
        result = runner.run_blocking(request)
    assert result.success is True
    job = store.list_jobs(limit=1)[0]
    assert job.state is TranscriptionJobState.SUCCEEDED
    assert job.succeeded_count == 1


@pytest.mark.unit
def test_run_blocking_records_cancel(tmp_path: Path) -> None:
    from transcriptx.app.models.errors import TranscriptionCancelled

    store = TranscriptionJobStore(tmp_path / "jobs")
    runner = reset_transcription_runner_for_tests(store)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"x")
    request = TranscriptionRequest(
        input_paths=[audio],
        transcription_options=TranscriptionOptions(
            provider_id="whispermlx",
            model="tiny",
            language="en",
            diarize=False,
        ),
        conversion_options=TranscriptionConversionOptions(),
        import_into_library=False,
    )
    with patch(
        "transcriptx.services.transcription.runner.TranscriptionController"
    ) as ctrl_cls:
        ctrl_cls.return_value.run_transcription.side_effect = TranscriptionCancelled(
            "stopped"
        )
        result = runner.run_blocking(request)
    assert result.success is False
    job = store.list_jobs(limit=1)[0]
    assert job.state is TranscriptionJobState.CANCELLED


@pytest.mark.unit
def test_drain_queued_watcher_jobs_submits(tmp_path: Path, monkeypatch) -> None:
    from transcriptx.services.transcription.runner import drain_queued_watcher_jobs
    from transcriptx.services.watcher.job_store import JobState, JobStore

    audio = tmp_path / "queued.mp3"
    audio.write_bytes(b"x")
    wstore = JobStore(tmp_path / "watcher" / "jobs")
    wjob = wstore.create(
        path=str(audio),
        basename=audio.name,
        state=JobState.QUEUED_TRANSCRIPTION,
        kind="audio",
    )
    tstore = TranscriptionJobStore(tmp_path / "stt" / "jobs")
    runner = reset_transcription_runner_for_tests(tstore)

    class _Svc:
        store = wstore

    monkeypatch.setattr(
        "transcriptx.services.transcription.registry.any_provider_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "transcriptx.services.watcher.service.get_watcher_service",
        lambda: _Svc(),
    )
    monkeypatch.setattr(
        "transcriptx.services.transcription.runner.get_transcription_runner",
        lambda: runner,
    )
    monkeypatch.setattr(
        "transcriptx.services.transcription.runner.build_transcription_request",
        lambda paths, **kwargs: TranscriptionRequest(
            input_paths=list(paths),
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="tiny",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
            import_into_library=True,
        ),
    )
    with patch.object(runner, "submit", wraps=runner.submit) as submit:
        with patch(
            "transcriptx.services.transcription.runner.TranscriptionController"
        ) as ctrl_cls:
            ctrl_cls.return_value.run_transcription.return_value = (
                TranscriptionBatchResult(
                    job_id="x",
                    success=True,
                    file_results=[],
                    succeeded_count=1,
                    failed_count=0,
                    output_dir=tmp_path,
                )
            )
            n = drain_queued_watcher_jobs(limit=5)
    assert n == 1
    assert submit.called
    refreshed = wstore.get(wjob.job_id)
    assert refreshed is not None
    assert refreshed.state is JobState.TRANSCRIBING
