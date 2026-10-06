"""Tests for durable transcription job store."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.services.transcription.job_store import (
    TranscriptionJobState,
    TranscriptionJobStore,
)


@pytest.mark.unit
def test_job_store_roundtrip(tmp_path: Path) -> None:
    store = TranscriptionJobStore(tmp_path / "jobs")
    job = store.create(
        provider_id="whispermlx",
        input_paths=["/a.wav"],
        model="tiny",
        language="en",
        diarize=False,
    )
    loaded = store.get(job.job_id)
    assert loaded is not None
    assert loaded.state is TranscriptionJobState.QUEUED
    assert loaded.provider_id == "whispermlx"
    store.update(loaded, state=TranscriptionJobState.RUNNING, progress_pct=40.0)
    store.append_log(loaded, "converting")
    again = store.get(job.job_id)
    assert again is not None
    assert again.state is TranscriptionJobState.RUNNING
    assert again.progress_pct == 40.0
    assert "converting" in again.logs


@pytest.mark.unit
def test_request_cancel(tmp_path: Path) -> None:
    store = TranscriptionJobStore(tmp_path / "jobs")
    job = store.create(provider_id="whispermlx", input_paths=["/a.wav"])
    store.request_cancel(job.job_id)
    loaded = store.get(job.job_id)
    assert loaded is not None
    assert loaded.cancel_requested is True
